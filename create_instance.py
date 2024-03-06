#!/usr/bin/env python3
import boto3
import webbrowser
import time
import random
import string
import json
import requests
import subprocess


#Function to genarate unique bucket name using random
def create_bucket_name(name):
    name = name.lower() # ensures name input is converted to lower case
    random_digits = ''.join(random.choices(string.digits, k=6))
    return f"{random_digits}-{name}"


# Create EC2 resource
ec2 = boto3.resource('ec2')

# Launch EC2 instance with User Data, MetaData to use  IMDSv2 and configure Apache
instances = ec2.create_instances(
    ImageId='ami-0440d3b780d96b29d',
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.nano',
    KeyName='HDip2024',
    SecurityGroupIds=['sg-03c4061af6e6cb8b6'],
    TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': 'DevOps Assignment 1'
                }
            ]
        }, 
    ],
    UserData="""#!/bin/bash
        # Update the system and install Apache
        yum update -y
        yum install httpd -y 
        # Start Apache and enable it
        systemctl enable httpd
        systemctl start httpd

        # HTML script with metadata
        echo '<html>' > index.html
        echo '<body>' >> index.html
        echo 'Availability zone: ' >> index.html
        TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/placement/availability-zone >> inde$
        echo '<br>Instance ID: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id >> index.html
        echo '<br>Instance Type: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-type >> index.html
        echo '</body>' >> index.html
        echo '</body>' >> index.html
        echo '</html>' >> index.html
        chmod 644 index.html
        cp index.html /var/www/html/index.html
        chmod 644 /var/www/html/index.html 
        """
)

           
# Print instance ID
print (f"Instance {instances[0].id} is launching. Please wait...")
            
# Wait for instance to start running
instance = instances[0]
instance.wait_until_running()
                 
# Reload instance to get public IP address
print("Initialising...")
instance.reload()
    
# Sleep to allow time for the Apache server to start
time.sleep(40)
        
# Use the instances public IP address as url for the Apache test page
apache_test_page_url = f'http://{instance.public_ip_address}'
print("Opening Apache test page:", apache_test_page_url)
webbrowser.open_new_tab(apache_test_page_url)

# *************************************************************************************
# ***********************   Execute Monitoring Script *********************************
# *************************************************************************************

# Specify user and instance
host = f"ec2-user@{instance.public_ip_address}"

pem_key = "/Users/laura/HDip2024.pem"

full_path_to_ssh = "/usr/bin/ssh"

# Define the SCP command to copy the monitoring.sh script to the EC2 instance
scp_command = f"scp -o StrictHostKeyChecking=no -i {pem_key}  monitoring.sh {host}:."
print(f"Executing SCP command: {scp_command}")
subprocess.run(scp_command, shell=True, check=True)
print("Script copied successfully")

#Set script permissions
chmod_command =f"ssh -o StrictHostKeyChecking=no -i {pem_key} {host} chmod 700 monitoring.sh"

# Execute permissions
subprocess.run(chmod_command, shell=True, check=True)
print("Script permissions set successfully.")  

# Define the SSH command to execute the monitoring script
monitoring_command =f"ssh -o StrictHostKeyChecking=no -i {pem_key} {host} './monitoring.sh'"
print(f"Executing monitoring.sh ... ...")

# Execute the monitoring script and capture its output  
result = subprocess.run(monitoring_command, shell=True, check=True, capture_output=True, text=True)
        
print(result.stdout)

'''#Check that excection of script was successful and insert error handling
if result.returncode == 0:
    print("Monitoring script executed successfully")

    #split output into lines for better reading
    output_lines = result.stdout.splitlines()
    for line in output_lines:
        print(line)
else:
    print("Failed to execute monitoring script")
    print("Error details:")

    # Split stderr into lines for better readability
    error_lines = result.stderr.splitlines()
    for line in error_lines:
        print(line)'''
        
        
# *************************************************************************************
# ***********************   S3 BUCKET  ************************************************
# *************************************************************************************

# create s3 client and resource     
s3client = boto3.client('s3')
s3 = boto3.resource('s3')

# Generate unique bucket name
bucket_name = create_bucket_name("lmurray")   
 
try:
    # create the s3 bucket using client
    s3client.create_bucket(Bucket=bucket_name)
            
    # clear default policy settings 
    s3client.delete_public_access_block(Bucket=bucket_name)

    # Bucket policy to allow public read access
    bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                }
            ]
    }   
        
    # Impliment the public access policy
    s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))
    print(f"Public access policy applied to bucket {bucket_name}")

    #Static website hosting configuration
    website_configuration = {
            'ErrorDocument': {'Key': 'error.html'},
            'IndexDocument': {'Suffix': 'index.html'},
        }
    bucket_website = s3.BucketWebsite(bucket_name)
    bucket_website.put(WebsiteConfiguration=website_configuration)
    
    
    # Download the image
    image_url = 'http://devops.witdemo.net/logo.jpg'
    response = requests.get(image_url)
    if response.status_code == 200:
        # Upload the image to S3
        s3.Bucket(bucket_name).put_object(Key='logo.jpg', Body=response.content,ContentType='image/jpeg')
                    
        # Create and upload index.html
        index_html_content = """<html>
        <body>
            <img src="logo.jpg" alt="Logo">
        </body>
        </html>"""

        #Upload the index.html to S3 bucket
        s3.Bucket(bucket_name).put_object(Key='index.html', Body=index_html_content,ContentType='text/html')
        # Open S3 static page in web browser
        region = s3client.meta.region_name
        s3_website_url = f"http://{bucket_name}.s3-website-{region}.amazonaws.com"
        webbrowser.open(s3_website_url) 
        print(f"Bucket {bucket_name} created and website configured. Visit: {s3_website_url}")
    
        # File to save urls into text file
        file_name = 'LMurray-websites.txt'
        with open(file_name, 'w') as file:
            file.write(f'EC2 Apache test page URL: {apache_test_page_url}\n')
            file.write(f'S3 static website URL: {s3_website_url}\n')
         
        print(f"URLS written to {file_name}")
    
    
#error handling
except Exception as e:  
    print(f"An unexpected error occured: {e}")



