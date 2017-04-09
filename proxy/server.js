var fs =require('fs');
var twitterProxyServer = require('twitter-proxy');
var port = process.env.PORT || 5000;

function readFile(filename){
  var contents = fs.readFileSync(filename);
  return contents;
}

var data = readFile('credentials.json');
var credentialObj = JSON.parse(data);

twitterProxyServer({
  consumerKey: credentialObj['consumerKey'],
  consumerSecret: credentialObj['consumerSecret'],
  accessToken: credentialObj['accessToken'],
  accessTokenSecret: credentialObj['accessTokenSecret'],
  port: port.toString()
});
