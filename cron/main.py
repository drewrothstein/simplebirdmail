# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START app]
import base64
from datetime import datetime
from dateutil import parser
import logging
import os

# [START imports]
from google.cloud import storage
from google.appengine.api import app_identity
import googleapiclient.discovery

from flask import Flask, jsonify, render_template, request
from mailchimp3 import MailChimp
import mandrill
import requests
# [END imports]


DEBUG               = True
BUCKET              = 'simplebird'
API_PROXY           = 'https://<SOME_PROXY>'
KMS_LOCATION        = 'global'
KMS_KEYRING         = 'simplebird'
MAILCHIMP_LISTID    = '<SOME_LIST>'
MAILCHIMP_CRYPTOKEY = 'mailchimp'
MAILCHIMP_API_FILE  = 'mailchimp_api.encrypted'
MANDRILL_CRYPTOKEY  = 'mandrill'
MANDRILL_API_FILE   = 'mandrill_api.encrypted'
MANDRILL_TEMPLATE   = '<SOME_TEMPLATE>'
NUM_TWEETS_TO_FETCH = 50


app = Flask(__name__)

# Helpers
def _decrypt(project_id, location, keyring, cryptokey, cipher_text):
    """Decrypts and returns string from given cipher text."""
    print('Decrypting cryptokey: {}'.format(cryptokey))
    kms_client = googleapiclient.discovery.build('cloudkms', 'v1')
    name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
        project_id, location, keyring, cryptokey)
    cryptokeys = kms_client.projects().locations().keyRings().cryptoKeys()
    request = cryptokeys.decrypt(
        name=name, body={'ciphertext': cipher_text.decode('utf-8')})
    response = request.execute()
    return base64.b64decode(response['plaintext'])

def download_output(output_bucket, filename):
    """Downloads the output file from GCS and returns it as a string."""
    print('Downloading output file')
    client = storage.Client()
    bucket = client.get_bucket(output_bucket)
    output_blob = (
        'keys/{}'
        .format(filename))
    return bucket.blob(output_blob).download_as_string()
#

# Functions
twitter_users_global = {}

def get_subscribers(key):
    """Gets subscribers from MailChimp."""
    print('Making an API call to MailChimp')
    client = MailChimp('apikey', str(key).strip())
    members = client.lists.members.all(MAILCHIMP_LISTID,
                                       get_all=True,
                                       fields="members.email_address,members.merge_fields")
    return members

def format_data_for_mail(subscribers, tweets, frequency):
    """Format data for mailing via Mandrill."""
    mandrill_vars        = []
    mandrill_subscribers = []
    tweet_content        = []

    # Structure will be what Mandrill will expect:
    #  [ 
    #    {'rcpt': <MAIL>,
    #     'vars': [{'name': <FOO>, 'content': <BAR>}, {}]
    #    }, ...
    #  ]
    # Also create 'to' array for Mandrill of subscribers:
    #  'to': [
    #          {'email': <MAIL>}, ...
    #        ]

    # Iterate each subscriber
    for subscriber in subscribers['members']:
        email  = subscriber['email_address']
        handle = subscriber['merge_fields']['TWITTERHAN']
        subscriber_frequency = subscriber['merge_fields']['FREQUENCY']

        # Only create section if they have a non-empty handle
        if handle and subscriber_frequency == frequency and handle in twitter_users_global:
            name          = twitter_users_global[handle].get('name', '').encode('utf-8')
            verified      = twitter_users_global[handle].get('verified', '')
            profile_img   = twitter_users_global[handle].get('profile_img', '')
            tweet_content = tweets[handle]

            mandrill_subscribers.append({'email': email})
            mandrill_vars.append({'rcpt': email,
                                  'vars': [
                                    {
                                      'name': 'name',
                                      'content': name
                                    },
                                    {
                                      'name': 'verified',
                                      'content': verified
                                    },
                                    {
                                      'name': 'screen_name',
                                      'content': handle
                                    },
                                    {
                                      'name': 'profile_img',
                                      'content': profile_img
                                    },
                                    {
                                      'name': 'tweet',
                                      'content': tweet_content
                                    }
                                  ]
                                })

    return mandrill_vars, mandrill_subscribers

def parse_tweets(tweets, handle, frequency):
    """Parse just the necessary information out of a response."""
    tweet_ids = []

    for tweet in tweets:
        if tweet['user']['screen_name'] == handle:
            created_at = parser.parse(tweet['created_at']).replace(tzinfo=None)

            if frequency == 'Daily':
                frequency_days = 1
            elif frequency == 'Weekly':
                frequency_days = 7

            if (datetime.now() - created_at).days < frequency_days:
                # Save global information
                twitter_users_global[handle] = ({'name':        tweet['user']['name'],
                                                   # Save as empty string for false'y w/Handlebars
                                                 'verified':    ('', 'true')[tweet['user']['verified'] == 'true'],
                                                 'profile_img': tweet['user']['profile_image_url_https'].replace('_normal', '_reasonably_small'),
                                               })

                media_entities = tweet['entities'].get('media', '')
                if media_entities and media_entities[0]:
                    media_url = media_entities[0].get('media_url_https', '') + ':mosaic'
                else:
                    media_url = ''

                # Save per-handle
                tweet_ids.append({'id':              tweet['id_str'],
                                  'created_at':      unicode(created_at.replace(microsecond=0)),
                                  'text':            tweet['text'],
                                  'media_url':       media_url,
                                  'retweet_count':   tweet['retweet_count'],
                                  'favorites_count': tweet['favorite_count'],
                                 })

    return tweet_ids

def get_tweets(subscribers, frequency):
    """Gets tweets for a list of handles."""
    print('Getting the last {} tweets for each user'.format(NUM_TWEETS_TO_FETCH))
    handle_list = []
    tweet_dict = {}

    for subscriber in subscribers['members']:
        handle = subscriber['merge_fields']['TWITTERHAN']
        subscriber_frequency = subscriber['merge_fields']['FREQUENCY']
        if handle and handle not in handle_list:
            if subscriber_frequency == frequency:
                handle_list.append(handle)

    for handle in handle_list:
        r = requests.get(API_PROXY + '/1.1/statuses/user_timeline.json?screen_name='+
                                     '{}&count={}&include_entities=true'.format(handle, NUM_TWEETS_TO_FETCH))
        tweet_dict[handle] = parse_tweets(r.json(), handle, frequency)

    return tweet_dict

def get_credentials(cryptokey, filename):
    """Fetches credentials from KMS returning a decrypted API key."""
    credentials_enc = download_output(BUCKET, filename)
    credentials_dec = _decrypt(app_identity.get_application_id(),
                               KMS_LOCATION,
                               KMS_KEYRING,
                               cryptokey,
                               credentials_enc)
    return credentials_dec

def mailit(mandrill_vars, mandrill_subscribers, apikey):
    """Sends the mail using the Mandrill API."""
    try:
        mandrill_client = mandrill.Mandrill(str(apikey).strip())
        message = {
         'to': mandrill_subscribers,
         'merge_vars': mandrill_vars
        }
        result = mandrill_client.messages.send_template(
          template_name=MANDRILL_TEMPLATE,
          template_content=[],
          message=message)
    except (mandrill.Error, requests.exceptions.RequestException) as e:
        print('A mandrill error occurred: {0} - {1}'.format(e.__class__, e))

def runit(frequency):
    """Runs the task."""
    subscribers = get_subscribers(get_credentials(MAILCHIMP_CRYPTOKEY, MAILCHIMP_API_FILE))
    tweets = get_tweets(subscribers, frequency)
    mandrill_vars, mandrill_subscribers = format_data_for_mail(subscribers, tweets, frequency)
    
    if DEBUG:
        jsonify(mandrill_vars, mandrill_subscribers)
    
    mailit(mandrill_vars, mandrill_subscribers, get_credentials(MANDRILL_CRYPTOKEY, MANDRILL_API_FILE))
    return 'Sent Mail'
#


# [START run/daily]
@app.route('/run/daily')
def rundaily():
    return runit('Daily')
# [END run/daily]

# [START run/weekly]
@app.route('/run/weekly')
def runweekly():
    return runit('Weekly')
# [END run/weekly]

@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', 500
# [END app]
