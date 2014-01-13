from __future__ import division
from twython import Twython
from twython import TwythonStreamer
from collections import Iterable
from textblob import TextBlob
from urlparse import urlparse
import json
import shapefile
import pymysql
import datetime
import colorsys
import sys
import traceback
import os
import re

APP_KEY = os.environ['APP_KEY']
APP_SECRET = os.environ['APP_SECRET']
OAUTH_TOKEN = os.environ['OAUTH_TOKEN']
OAUTH_TOKEN_SECRET = os.environ['OAUTH_TOKEN_SECRET']

save_lag = 30
mood_lag = 30

sf = shapefile.Reader("states.shp")
starttime = datetime.datetime.now()
ws = "INSERT INTO tweets (state, sentiment, date) VALUES "
tweets = 0

def getDBCursor():
	db = urlparse(os.environ['DATABASE_URL'])
	if db.port:
		cnx = pymysql.connect(charset='utf8', host=db.hostname, port=db.port, user=db.username, passwd=db.password, db=db.path[1:])
	else:
		cnx = pymysql.connect(charset='utf8', host=db.hostname, user=db.username, passwd=db.password, db=db.path[1:])
	cursor = cnx.cursor()
	return (cursor, cnx)

def pip(x,y,poly):
    n = len(poly)
    inside = False
    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x,p1y = p2x,p2y
    return inside

def cleanDatabase():
	global save_lag
	cursor, cnx = getDBCursor()
	lag = datetime.datetime.now() - datetime.timedelta(minutes=save_lag)
	params = lag.isoformat(' ')
	rs = "DELETE FROM tweets WHERE `date` < '%s'" % (params)
	cursor.execute(rs)
	cnx.commit()
	cursor.close()
	cnx.close()
	print "Cleaned!"

def commitTweets():
	global ws
	print ws
	cursor, cnx = getDBCursor()
	cursor.execute(ws)
	cnx.commit()
	cursor.close()
	cnx.close()

def processTweet(tweet):
    #Convert to lower case
    tweet = tweet.lower()
    #Convert www.* or https?://* to URL
    tweet = re.sub('((www\.[\s]+)|(https?://[^\s]+))','URL',tweet)
    #Convert @username to AT_USER
    tweet = re.sub('@[^\s]+','AT_USER',tweet)    
    #Remove additional white spaces
    tweet = re.sub('[\s]+', ' ', tweet)
    #Replace #word with word
    tweet = re.sub(r'#([^\s]+)', r'\1', tweet)
    #trim
    tweet = tweet.strip('\'"')
    return tweet

class MyStreamer(TwythonStreamer):

	def on_success(self, data):
		global starttime
		global tweets
		global ws
		if 'coordinates' in data:
			state = "nil"
			try:
				if isinstance(data['coordinates'], Iterable):
					if 'coordinates' in data['coordinates']:
							lat = data['coordinates']['coordinates'][0]
							lon = data['coordinates']['coordinates'][1]
							
							for st in sf.shapeRecords():
								if pip(lat, lon, st.shape.points):
									state = st.record[31]
									break

				elif 'place' in data and isinstance(data['place'], Iterable):
					if data['place']['country_code'] == 'US':
						state = data['place']['full_name'][-2:]
						print state


				if ('text' in data) and (state != 'nil'):
					text = processTweet(data['text'])
					analysis = TextBlob(text)
					if analysis.sentiment.polarity != 0:
						if tweets > 0:
							ws += ", "
						ws += """('%s', %s, NOW())""" % (state, analysis.sentiment.polarity)
						tweets += 1
						print tweets
					if (datetime.datetime.now() - starttime).total_seconds() > 15:
						print "Commit!"
						commitTweets()
						cleanDatabase()
						starttime = datetime.datetime.now()
						tweets = 0
						ws = "INSERT INTO tweets (state, sentiment, date) VALUES "

			except Exception as e:
				print e

	def on_error(self, status_code, data):
		print status_code

def stream():
	stream = MyStreamer(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
	#stream.statuses.filter(locations='-124.7625,24.5210,-66.9326,49.3845,-171.7911,54.4041,-129.9799,71.3577,-159.8005,18.9161,-154.8074,22.2361')
	stream.statuses.filter(track='golden globes, globes, hollywood foreign press, gg, red carpet, nbc')
	
stream()