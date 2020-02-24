import json
import boto3
from datetime import datetime
from decimal import Decimal

bucket = "uploaded-images-for-rekognition" 
model='arn:aws:rekognition:us-east-1:964394112301:project/BirdRecognition/version/BirdRecognition.2020-02-23T01.59.29/1582394369894'
min_confidence=60

	

def lambda_handler(event, context):
	if event:
		file_obj = event["Records"][0]
		bucketname = str(file_obj['s3']['bucket']['name'])
		filename = str(file_obj['s3']['object']['key'])
		print("Filename: ", filename)
		client=boto3.client('rekognition')
		#Call DetectCustomLabels 
		response = client.detect_custom_labels(Image={'S3Object': {'Bucket': bucket, 'Name': filename}},MinConfidence=min_confidence,ProjectVersionArn=model)
		# calculate and display bounding boxes for each detected custom label       
		print('Detected custom labels for ' + filename)
		Labellist = []
		confidencelist = []
		for customLabel in response['CustomLabels']:
			labelling=(customLabel['Name'])
			Labellist.append(labelling)
			confidencevalue=(customLabel['Confidence'])
			confidencelist.append(confidencevalue)
		if len(Labellist) > 0:
			highest= confidencelist.index(max(confidencelist))
			highlabel=(Labellist[highest])
			highconfidence=(confidencelist[highest])
			filenamelist=filename.split("_")
			dynamodb = boto3.resource('dynamodb')
			table = dynamodb.Table('Photodetect')
			now = datetime.now()
			response = table.put_item(
			Item={
			'ID': "1",
	        'datetime': now.isoformat(),
	        'DeviceID': filenamelist[0],
	        'filename': filename,
	        'label': highlabel,
	        'confidence': Decimal(highconfidence)
	    	})
			print("Successful Upload")
		else:
			print("No Birds Detected")