import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config['AWS_REGION']
        )
        self.bucket_name = current_app.config['S3_BUCKET']
    
    def generate_s3_key(self, table_name, date_from, date_to, reference_id):
        """Generate S3 key following the naming convention"""
        return f"exports/{table_name}/{date_from}_{date_to}/{reference_id}.csv"
    
    def upload_file(self, file_path, s3_key):
        """Upload a file to S3 using multipart upload for large files"""
        try:
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Use multipart upload for files larger than 100MB
            if file_size > 100 * 1024 * 1024:  # 100MB
                return self._multipart_upload(file_path, s3_key)
            else:
                return self._simple_upload(file_path, s3_key)
                
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except ClientError as e:
            logger.error(f"AWS S3 error: {str(e)}")
            raise
    
    def _simple_upload(self, file_path, s3_key):
        """Simple upload for smaller files"""
        self.s3_client.upload_file(
            file_path, 
            self.bucket_name, 
            s3_key,
            ExtraArgs={
                'ContentType': 'text/csv',
                'ContentDisposition': f'attachment; filename="{os.path.basename(s3_key)}"'
            }
        )
        
        s3_url = f"s3://{self.bucket_name}/{s3_key}"
        logger.info(f"Successfully uploaded file to S3: {s3_url}")
        return s3_url
    
    def _multipart_upload(self, file_path, s3_key):
        """Multipart upload for larger files"""
        # Initialize multipart upload
        response = self.s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
            ContentType='text/csv',
            ContentDisposition=f'attachment; filename="{os.path.basename(s3_key)}"'
        )
        
        upload_id = response['UploadId']
        parts = []
        part_number = 1
        chunk_size = 100 * 1024 * 1024  # 100MB chunks
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Upload part
                    part_response = self.s3_client.upload_part(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk
                    )
                    
                    parts.append({
                        'ETag': part_response['ETag'],
                        'PartNumber': part_number
                    })
                    
                    part_number += 1
                    logger.info(f"Uploaded part {part_number - 1} for {s3_key}")
            
            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Successfully completed multipart upload to S3: {s3_url}")
            return s3_url
            
        except Exception as e:
            # Abort multipart upload on error
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id
            )
            logger.error(f"Multipart upload failed, aborted: {str(e)}")
            raise
    
    def generate_presigned_url(self, s3_url):
        """Generate a pre-signed URL for downloading the file"""
        try:
            # Extract S3 key from URL
            if s3_url.startswith('s3://'):
                # Parse s3://bucket/key format
                parsed = urlparse(s3_url)
                s3_key = parsed.path.lstrip('/')
            else:
                # Assume it's already a key
                s3_key = s3_url
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=current_app.config['PRESIGNED_URL_EXPIRATION']
            )
            
            logger.info(f"Generated presigned URL for {s3_key}")
            return presigned_url
            
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            raise
    
    def delete_file(self, s3_url):
        """Delete a file from S3"""
        try:
            # Extract S3 key from URL
            if s3_url.startswith('s3://'):
                parsed = urlparse(s3_url)
                s3_key = parsed.path.lstrip('/')
            else:
                s3_key = s3_url
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Deleted file from S3: {s3_key}")
            
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            raise