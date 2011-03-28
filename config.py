''' Simple Configuration for IRC Bot named Annuska '''
''' Server and the port where the bot is to be hosted '''
irc_settings = {
	'server':'irc.freenode.com',
	'port': 6697,
	'username' : '',
	'password' : '',
	'nick' : 'Annuska',
	'nick_password' : '<nick_password>',
	'ssl': False,
	'channels': '#channels',
}

web_api = {
	'host': 'localhost',
	'path': 'irclogs',
}

'''Elasticserver settings'''
es_settings = {
	'Server':'127.0.0.1:9200',
	'Index' : 'irclogs',
}
