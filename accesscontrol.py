from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from picamera import PiCamera
import argparse
import boto3
import time
import datetime
import os
import RPi.GPIO as GPIO
from pn532 import *
from functions import Speak
from functions import takePhoto
from functions import RegisterImageToRekognition
from functions import GetNameFromRFID
from functions import processRekognitionJSON
from functions import customCallback
from functions import publishMQTT
from functions import ConfigureAndSubscribeMQTT




if __name__ == '__main__':

    myAWSIoTMQTTClient, topic= ConfigureAndSubscribeMQTT()
    seq=0

    parser = argparse.ArgumentParser(description='Specify Access Control User group (collection).')
    parser.add_argument('--collection', help='Collection Name', default='fotis-faces2')
    args = parser.parse_args()


    camera = PiCamera()
    camera.resolution = (800, 600)
    camera.awb_mode = 'auto'

    ACCESS_KEY= os.getenv('AWS_ACCESS_KEY')
    SECRET_KEY= os.getenv('AWS_SECRET_KEY')
    
    polly = boto3.client('polly',aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,region_name='us-east-1')
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
    rekog = boto3.client('rekognition', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,region_name='us-east-1')

    #key code used for entering registration mode
    registration_card_name='1-35-69-103'
    name=''
    try:
        pn532 = PN532_SPI(debug=False, reset=20, cs=4)
        ic, ver, rev, support = pn532.get_firmware_version()

        # Configure PN532 to communicate with MiFare cards
        pn532.SAM_configuration()

        Speak('Please scan your NFC card...',polly)
        
        registration_mode=False

        while True:
            # Check if a card is available to read 
            uid = pn532.read_passive_target(timeout=1)
            print(".")
            if uid is None:
                continue
            os.system('omxplayer_silent {}'.format("sounds/scan.mp3"))
            name= GetNameFromRFID(uid)
            print(name)
            if name==registration_card_name:
                registration_mode=True
                Speak('Registration mode activated. Please scan you card first.',polly)
            else:
                #Registration
                if registration_mode:
                    Speak('Your card is captured.',polly)
                    Speak('Photo in three, two, one.',polly)
                    image= takePhoto('faces',name,camera)
                    
                    RegisterImageToRekognition(image,name,args.collection,rekog)

                    with open(image, mode='rb') as file1:
                        b_a_jpg = bytearray(file1.read())
                        try:
                            response = rekog.detect_faces(Image={'Bytes': b_a_jpg}, Attributes=['ALL'])
                            # print(json.dumps(response, indent = 1))
                            gender, emotion, age_range_low,age_range_high= '','','',''
                            if len(response["FaceDetails"]) >=1:
                                gender, emotion, age_range_low,age_range_high = processRekognitionJSON(response)  
                                age = age_range_low+(age_range_high - age_range_low)/2
                                responseIndex = rekog.index_faces(Image={'Bytes': b_a_jpg}, CollectionId=args.collection, ExternalImageId=name, DetectionAttributes=['ALL'])
                                Speak("You are {0}, around {1} years old and you feel {2}" .format(gender, age_range_low, emotion),polly)
                                Speak('Registration completed. Thank you.',polly)
                                
                                registration_mode=False
                                #Publish registration to MQTT topic   
                                publishMQTT(myAWSIoTMQTTClient, topic,seq,'Key ' + name +' has been registered successfully with Photo ' +image)
                                seq+=1
                               
                            else:
                                Speak('Registration failed. Please try again.',polly)
                        except Exception:
                            #   print(Exception.message)
                              Speak('Registration failed. Please try again.',polly)

                #Access Control (1) with Rekognition 
                else:
                    dt_date = datetime.datetime.now()
                    filepath=dt_date.strftime('pic'+name+"_%y%m%d%H%M%S")
                    Speak('Taking Photo',polly)
                    image= takePhoto('pictures',filepath,camera)

                    face_matched = False
                    with open(image, 'rb') as file:
                        try:
                            b_a_jpg = bytearray(file.read())
                            response = rekog.search_faces_by_image(CollectionId=args.collection, Image={'Bytes': b_a_jpg}, MaxFaces=1, FaceMatchThreshold=85)
                            if (not response['FaceMatches']):
                                face_matched = False
                            else:
                                face_matched = True
                        except:
                            Speak('Face not recognized, please try again',polly)
                            continue

                 
                    if (face_matched):
                        if response["FaceMatches"][0]["Face"]["ExternalImageId"] != name:
                            os.system('omxplayer_silent {}'.format("sounds/error.mp3"))
                            Speak("Your key does not match the registered one.",polly)
                            Speak("You cannot enter.",polly)
                            publishMQTT(myAWSIoTMQTTClient, topic,seq,'Key ' + name +' was denied')
                            seq+=1
                        else:
                            os.system('omxplayer_silent {}'.format("sounds/triumphant.mp3"))
                            Speak("Welcome, please come in.",polly)
                            publishMQTT(myAWSIoTMQTTClient, topic,seq,'Key ' + name +' was accepted')
                            seq+=1

                   
                    else:
                        os.system('omxplayer_silent {}'.format("sounds/error.mp3"))
                        Speak("You were not recognized in the database.",polly)
                        Speak("You cannot enter.",polly)

                    #Access Control (2) with AWS Lambda, Rekognition and MQTT
                    try:
                        
                        #Uploads image to S3 to automatically processed with Lambda (lambda_function.py) and Recognition in AWS, results are published to MQTT and can be read from Raspberry to control access
                        #result = s3.get_bucket_acl(Bucket='accesscontrolpictures')
                        s3.upload_file(image, 'accesscontrolpictures', image)
                        print("Upload Successful")
                    except FileNotFoundError:
                        print("The file was not found")
                    except NoCredentialsError:
                        print("Credentials not available")
                    except AccessDenied:  
                        print("AccessisDenied")
            
    except BaseException as e:
        print(e.message)
    finally:
        GPIO.cleanup()
        camera.close()
    
    

  