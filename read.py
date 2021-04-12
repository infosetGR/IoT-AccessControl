
import RPi.GPIO as GPIO
import datetime
import os
import boto3
from botocore.exceptions import NoCredentialsError

from pn532 import *
from picamera import PiCamera


if __name__ == '__main__':
    try:
        camera = PiCamera()
        camera.resolution = (800, 600)
        camera.awb_mode = 'auto'


        pn532 = PN532_SPI(debug=False, reset=20, cs=4)
        ic, ver, rev, support = pn532.get_firmware_version()
        #print('Found PN532 with firmware version: {0}.{1}'.format(ver, rev))

        # Configure PN532 to communicate with MiFare cards
        pn532.SAM_configuration()

        print('Waiting for RFID/NFC card...')
        
        name=''
        while True:
            
            # Check if a card is available to read 
            uid = pn532.read_passive_target(timeout=1)
            #print('.', end="")
            print('.')
            # Try again if no card is available.
            
            # input
         
            if uid is None or "-".join(str(n) for n in uid) == name:
                continue
            
            print('Found card with UID:', [hex(i) for i in uid],[i for i in uid])
            print('Taking picture')
            
            dt_date = datetime.datetime.now()
            name="-".join(str(n) for n in uid)
            filepath=dt_date.strftime('pic'+name+"_%y%m%d%H%M%S")+'.png'
            camera.capture(filepath)
          
            print(filepath)

            ACCESS_KEY= os.getenv('AWS_ACCESS_KEY')
            SECRET_KEY= os.getenv('AWS_SECRET_KEY')

            s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
            #result = s3.get_bucket_acl(Bucket='accesscontrolpictures')
            #print(result)
            try:
                s3.upload_file(filepath,  'accesscontrolpictures', filepath)
                print("Upload Successful")
            except FileNotFoundError:
                print("The file was not found")
            except NoCredentialsError:
                print("Credentials not available")
            except AccessDenied:  
                print("AccessisDenied")
    
            if os.path.exists(filepath):
                os.remove(filepath)
    finally:
        GPIO.cleanup()
        camera.close()
 