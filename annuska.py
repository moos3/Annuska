
#!/usr/bin/env python
__author__ = "Moose <richard@guthnur.net>"
__license__ = "GPLV2"
__version__ = "1.0"

''' A PY IRC bot with functionalities like:
    * Google I'm feeling lucky search
    * XCKD random images
    * Flipping a coin, throwing the dice
	* Logging to falt file
	* Loggin to ElasticSearch
'''

import sys, operator, math, re, random, os, urllib, json, datetime, BeautifulSoup, pyes, pprint
from twisted.internet import ssl, reactor, task, defer, protocol
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.web.client import getPage, Agent
from twisted.application import internet, service
from twisted.web import google, client
from twisted.web.http_headers import Headers
from config import irc_settings, web_api, es_settings

''' RPN calc map operator symbol tuple of # and function '''
calc_operators = {
    '+': (2, operator.add),
    '-': (2, operator.sub),
    '*': (2, operator.mul),
    '/': (2, operator.truediv),
    '//': (2, operator.div),
    '%': (2, operator.mod),
    '^': (2, operator.pow),
    'abs': (1, abs),
    'ceil': (1, math.ceil),
    'floor': (1, math.floor),
    'round': (2, round),
    'trunc': (1, int),
    'log': (2, math.log),
    'ln': (1, math.log),
    'pi': (0, lambda: math.pi),
    'e': (0, lambda: math.e),
}

class AnnuskaIRC(irc.IRCClient):
    ''' The nick name of the bot '''
    nickname = irc_settings['nick']
    username = irc_settings['username']
    password = irc_settings['password']

    ''' After server has acknowledged the nick '''
    def signedOn(self):
        self.join(self.factory.channels)

    ''' When a PM is recived '''
    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        if channel != self.nickname and not message.startswith(self.nickname):
			filename = channel+"-"+datetime.datetime.now().strftime("%Y-%m-%d")
            # We can LOG here :)
			file = open(filename, 'a')
			file.writelines(datetime.datetime.now().strftime("%Y-%m-%d [%H:%M]")+" "+nick+" : "+message+"\n")
			#send_to_elastic(self, es_setttings, user, channel, message)
			return
        # Strip off any addressing.
        message = re.sub(
            r'^%s[.,>:;!?]*\s*' % re.escape(self.nickname), '', message)
        command, _, rest = message.partition(' ')

        # Get the function
        func = getattr(self, 'command_' + command, None)

        # IF not a defined function
        if func is None:
            self.msg(channel, "%s,I cant understand what %s means, but you can teach me, catch me @ http://github.com/moos3/Annuska" % (nick,message))
            return

        d = defer.maybeDeferred(func, rest)
        if channel == self.nickname:
            args = [nick]

        # If there is rediction request made in the bot query.
        elif len(rest.split('>')) > 1:
            args = [channel, rest.split('>')[1]]
        else:
            args = [channel, nick]
        d.addCallbacks(self._send_message(*args), self._show_error(*args))
        return message

	def logMessage(self, user, channel, message):
		nick, _, host = user.partition('!')
		# we write file and send to elastic search
		filename = channel+"_"+datetime.datetime.now().strftime("%Y-%m-%d")
		timestamp = datetime.datetime.now().strftime("%Y-%m-%d [%H:%M]")
		logline = "["+channel+"]  "+timestamp+" "+nick+": "+message+"\n"
		#file = open(filename, 'a')
		#file.writelines(line)
		#send_to_elastic(self,es_settings,user,channel,message,timestamp)
		return

    def _send_message(self, target, nick=None):
        def callback(msg):
            print target
            if nick:
                msg = '%s, %s' % (nick, msg)
            self.msg(target, msg)
        return callback

    def _show_error(self, target, nick=None):
        def errback(f):
            msg = f.getErrorMessage()
            if nick:
                msg = '%s, %s' % (nick, msg)
            self.msg(target, msg)
            return f
        return errback

    ''' Command_xxx corresponds to factoids of the bot '''

    def command_help(self,rest):
        ''' Just returns the help msg, to the user who pinged with help '''
        return "Try peep <url>,goog <str>, xkcd, flip, roll, logs <channelName>, tell"

    def command_hi(self,rest):
        return "Hello :)"

	def command_tell(self,rest):
		return "I'm a bot sent from the future to protect your IRC logs, Please use command help to learn more, I'm currently running version "+__version__

    def _get_page_content(self,page,url):
         return page

    def command_flip(self,rest):
        return random.choice(('head', 'tail'))

    def command_roll(self,rest):
        return random.choice((1,2,3,4,5,6))

    def command_fortune(self,rest):
        return os.popen('fortune -n 111').read().translate(None, '\n\r\t')

    def command_goog(self,rest):
        ''' rest is the rest of the query for goog <str> passed by the user
            that is encoded and is queried with the help of google search
            API, a callback is added after getpage() '''
        if(rest == "" or rest == " "):
           rest = "google"
        query = urllib.urlencode({'q': rest})
        url = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&%s' % query
        search_response_d = getPage(url)
        search_response_d.addCallback(self._get_json_results,url)
        return search_response_d

    def _get_json_results(self,page,url):
        ''' The return value from Google API is json,
            from which the first link is extracted '''
        search_results = page.decode("utf8")
        results = json.loads(search_results)
        return "".join(str(results['responseData']['results'][0]['url']))

    def command_peep(self, url):
        d = getPage(url)
        d.addCallback(self._parse_pagetitle, url)
        return d

    def command_xkcd(self,rest):
        ''' Agent is used to get the redirected URL
             /random/comic will redirect to a new
             comic that is fetched from cbRequest '''
        agent = Agent(reactor)
        d = agent.request(
        'GET',
        'http://dynamic.xkcd.com/random/comic/',
        Headers({'User-Agent': ['Twisted Web Client Example']}),
        None)
        d.addCallback(self.cbRequest)
        return d

    def cbRequest(self,response):
         ''' Get the redirected url is retrieved from getRawHeaders() '''
         return "".join(response.headers.getRawHeaders("location")) + " Enjoy it!"


    def _parse_pagetitle(self, page, url):
        ''' Get the page title '''
        head_tag = BeautifulSoup.SoupStrainer('head')
        soup = BeautifulSoup.BeautifulSoup(page,
            parseOnlyThese=head_tag, convertEntities=['html', 'xml'])
        if soup.title is None:
            return '%s -- no title found' % url
        title = unicode(soup.title.string).encode('utf-8')
        return '%s -- "%s"' % (url, title)

    def command_calc(self, rest):
        '''RPN calculator!'''
        stack = []
        for tok in rest.split():
            if tok in calc_operators:
                n_pops, func = calc_operators[tok]
                args = [stack.pop() for x in xrange(n_pops)]
                args.reverse()
                stack.append(func(*args))
            elif '.' in tok:
                stack.append(float(tok))
            else:
                stack.append(int(tok))
        result = str(stack.pop())
        if stack:
            result += ' (warning: %d item(s) left on stack)' % len(stack)
        return result

	def command_moose(self,rest):
		return "Moose is Awesome"

class AnnuskaIRCactory(protocol.ReconnectingClientFactory):
    protocol = AnnuskaIRC
    channels = irc_settings['channels']

if __name__ == '__main__':
	if irc_settings['ssl'] == True:
		contextFactory = ssl.ClientContextFactory()
		reactor.connectSSL(irc_settings['server'], irc_settings['port'], AnnuskaIRCactory(), contextFactory)
	else:
		reactor.connectTCP(irc_settings['server'], irc_settings['port'], AnnuskaIRCactory())

	log.startLogging(sys.stdout)
	reactor.run()

elif __name__ == '__builtin__':

    application = service.Application('AnnuskaIRCBot')

    ircService = internet.TCPClient(irc_settings['server'], irc_settings['port'], AnnuskaIRCactory())
    ircService.setServiceParent(application)
