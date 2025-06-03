from azure.storage.blob import BlobServiceClient
import json
from datetime import datetime, time
import pandas as pd
import numpy as np

class StorageManager:
    def __init__(self, connection_string):
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = "test-results"
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
        
        # Ensure container exists
        try:
            self.container_client.create_container()
        except:
            pass

    def _serialize_data(self, obj):
        """Convert non-serializable types to serializable ones"""
        if isinstance(obj, (datetime, pd.Timestamp, time)):
            return obj.isoformat()
        elif isinstance(obj, (pd.Series, pd.DataFrame)):  # Handle pandas objects
            return obj.to_dict()
        elif isinstance(obj, (list, tuple, np.ndarray)):  # Handle array-like objects
            return [self._serialize_data(item) for item in obj]
        elif hasattr(obj, 'dtype'):  # Handle numpy scalars
            return obj.item()
        elif pd.isna(obj):  # Handle pandas NA/NaN
            return None
        elif isinstance(obj, dict):
            return {k: self._serialize_data(v) for k, v in obj.items()}
        elif hasattr(obj, '__dict__'):  # Handle custom objects
            return str(obj)
        return obj

    def save_test_result(self, email, results):
        """Save test results to blob storage"""
        blob_name = f"test_results/test_results_{email}.json"
        blob_client = self.container_client.get_blob_client(blob_name)
        
        try:
            # Get and clean existing data
            existing_data = self.get_test_results(email)
            existing_data = [self._serialize_data(item) for item in existing_data]
            
            # Clean and add new results
            new_data = self._serialize_data(results)
            existing_data.extend([new_data] if not isinstance(new_data, list) else new_data)
            
            # Upload the cleaned data
            blob_client.upload_blob(json.dumps(existing_data), overwrite=True)
            
        except Exception as e:
            # If no existing data, start fresh
            new_data = self._serialize_data(results)
            data_to_save = [new_data] if not isinstance(new_data, list) else new_data
            blob_client.upload_blob(json.dumps(data_to_save), overwrite=True)

    def get_test_results(self, email):
        """Get test results from blob storage"""
        blob_name = f"test_results/test_results_{email}.json"
        blob_client = self.container_client.get_blob_client(blob_name)
        
        try:
            data = blob_client.download_blob().readall()
            # Clean the data when reading
            return [self._serialize_data(item) for item in json.loads(data)]
        except:
            return []

    def list_users(self):
        """List all users with test results"""
        users = []
        for blob in self.container_client.list_blobs():
            if blob.name.startswith("test_results/test_results_"):
                email = blob.name.replace("test_results/test_results_", "").replace(".json", "")
                users.append(email)
        return users

    def download_json(self, email):
        """Get raw JSON for a user"""
        blob_name = f"test_results/test_results_{email}.json"
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()