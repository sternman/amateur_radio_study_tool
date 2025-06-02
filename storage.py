from azure.storage.blob import BlobServiceClient
import json

class StorageManager:
    def __init__(self, connection_string):
        
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = "carst"
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
        
        # Ensure container exists
        try:
            self.container_client.create_container()
        except:
            pass

    def save_test_result(self, email, results):
        """Save test results to blob storage"""
        blob_name = f"test_results/test_results_{email}.json"
        blob_client = self.container_client.get_blob_client(blob_name)
        
        # Get existing results if any
        try:
            existing_data = self.get_test_results(email)
            existing_data.extend(results if isinstance(results, list) else [results])
            data_to_save = existing_data
        except:
            data_to_save = results if isinstance(results, list) else [results]
        
        # Upload the updated results
        blob_client.upload_blob(json.dumps(data_to_save), overwrite=True)

    def get_test_results(self, email):
        """Get test results from blob storage"""
        blob_name = f"test_results/test_results_{email}.json"
        print(blob_name)
        blob_client = self.container_client.get_blob_client(blob_name)
        
        try:
            data = blob_client.download_blob().readall()
            return json.loads(data)
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