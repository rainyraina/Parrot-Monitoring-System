#!/usr/bin/python3
#from app import app
from flask import Flask, flash, redirect, render_template, request, session, abort, jsonify
import gevent
import gevent.monkey
import time
import base64
import numpy
from boto3.dynamodb.conditions import Key, Attr
import sys
import json
import decimal 
from decimal import Decimal
import boto3
import botocore
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import datetime as datetime
app = Flask(__name__)
from gevent.pywsgi import WSGIServer
gevent.monkey.patch_all()

#MQTT
host = "a1hdsuh2fiycts-ats.iot.us-east-1.amazonaws.com"
rootCAPath = "Server/AmazonRootCA1.pem"
certificatePath = "Server/certificate.pem.crt"
privateKeyPath = "Server/private.pem.key"

my_rpi = AWSIoTMQTTClient("basicPubSub")
my_rpi.configureEndpoint(host, 8883)
my_rpi.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

my_rpi.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
my_rpi.configureDrainingFrequency(2)  # Draining: 2 Hz
my_rpi.configureConnectDisconnectTimeout(10)  # 10 sec
my_rpi.configureMQTTOperationTimeout(5)  # 5 sec
my_rpi.connect()

def get_latest_file_name(bucket_name,prefix):
    """
    Return the latest file name in an S3 bucket folder.

    :param bucket: Name of the S3 bucket.
    :param prefix: Only fetch keys that start with this prefix (folder  name).
    """
    s3_client = boto3.client('s3')
    objs = s3_client.list_objects_v2(Bucket=bucket_name)['Contents']
    shortlisted_files = dict()            
    for obj in objs:
        key = obj['Key']
        timestamp = obj['LastModified']
        # if key starts with folder name retrieve that key
        if key.startswith(prefix):              
            # Adding a new key value pair
            shortlisted_files.update( {key : timestamp} )   
    latest_filename = max(shortlisted_files, key=shortlisted_files.get)
    return latest_filename

class GenericEncoder(json.JSONEncoder):
	def default(self, obj):  
		if isinstance(obj, numpy.generic):
			return numpy.asscalar(obj)
		elif isinstance(obj, Decimal):
			return str(obj) 
		elif isinstance(obj, datetime.datetime):  
			return obj.strftime('%Y-%m-%d %H:%M:%S') 
		elif isinstance(obj, Decimal):
			return float(obj)
		elif isinstance(obj, decimal.Decimal):
			return (str(object) for object in [obj])
		else:  
			return json.JSONEncoder.default(self, obj)
			
def data_to_json(data):
	json_data = json.dumps(data, cls=GenericEncoder)
	return json_data


def getdynamodb(tablename,DeviceID):
	try:
		dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
		table = dynamodb.Table(tablename)
		startdate = '2020-02'
		response = table.query(
			KeyConditionExpression=Key('DeviceID').eq(DeviceID) & Key('datetime').begins_with(startdate),ScanIndexForward=False)
		items = response['Items']
		items.reverse()
		return (data_to_json(items))
		
	except:
		print(sys.exc_info()[0])
		print(sys.exc_info()[1])

def getdynamodb2():
	try:
		dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
		table = dynamodb.Table("Photodetect")
		startdate = '2020-02'
		response = table.query(
			KeyConditionExpression=Key('ID').eq("1") & Key('datetime').begins_with(startdate), ScanIndexForward=False,Limit=1)
		items = response['Items']
		return (data_to_json(items))
		
	except:
		print(sys.exc_info()[0])
		print(sys.exc_info()[1])

@app.route('/api/latestphoto', methods=['GET','POST'])			
def latestphoto():
	photoupload= getdynamodb2()
	photouploadjson= json.loads(photoupload)
	values=[]
	for x in photouploadjson:
		values.append(x['DeviceID'])
		values.append(x['filename'])
		values.append(x['datetime'])
		values.append(x['label'])
		values.append(x['confidence'])
	print(values)
	BUCKET_NAME = 'uploaded-images-for-rekognition'
	s3 = boto3.client('s3')
	try:
		s3.download_file(BUCKET_NAME, values[1], 'image.jpg')
		with open("image.jpg", "rwb") as image_file:
			image = base64.b64encode(image_file.read())
			photo ={
			"DeviceID": values[0],
			"filename" : values[1],
			"datetime": values[2],
			"label": values[3],
			"confidence": values[4],
			"image" : image,
			}
		return jsonify(photo)

	except botocore.exceptions.ClientError as e:
		if e.response['Error']['Code'] == "404":
			print("The object does not exist.")
		else:
			raise

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')
	
@app.route('/api/WMSsensors', methods=['GET','POST'])
def WMSsensors():
	data = getdynamodb("WaterMonitoringStation","WMS1")
	return data

@app.route('/api/FMSsensors', methods=['GET','POST'])
def FMSsensors():
	data = getdynamodb("FoodMonitoringStation","FMS1")
	return data
	
@app.route('/api/updatefeed', methods=['GET','POST'])
def updatefeed():
	data = getdynamodb("FeedingStation","FMS1")
	return data
	
@app.route('/api/updaterefill', methods=['GET','POST'])
def refillstation():
	data = getdynamodb("RefillStation","WMS1")
	return data
			
@app.route('/api/refill', methods=['GET','POST'])			
def publishmqttrefill():
	value = request.args.get('value')
	print(value)
	message = {}
	message["DeviceID"] = "WMS1"
	now = datetime.datetime.now()
	message["datetime"] = now.isoformat()      
	message["refill"] = value
	my_rpi.publish("monitor/WMS/refill", json.dumps(message), 1)
	return(value)

@app.route('/api/feed', methods=['GET','POST'])
def publishmqttfeed():
	message = {}
	message["DeviceID"] = "FMS1"
	now = datetime.datetime.now()
	message["datetime"] = now.isoformat()      
	message["feed"] = "1"
	my_rpi.publish("monitor/FMS/feed", json.dumps(message), 1)	
	return("feed")
	
	
if __name__ == '__main__':
  try:
    print('Server waiting for requests')
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    app.debug = True
    http_server.serve_forever()
  except:
    print("Exception")
    import sys
    print(sys.exc_info()[0])
    print(sys.exc_info()[1])



	
	