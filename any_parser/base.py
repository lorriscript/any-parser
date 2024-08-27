import time
import requests
from datetime import datetime, timedelta
from any_parser.postprocessors import run_convert


CAMBIO_UPLOAD_URL = "https://jnrsqrod4j.execute-api.us-west-2.amazonaws.com/v1/upload"
CAMBIO_REQUEST_URL = "https://jnrsqrod4j.execute-api.us-west-2.amazonaws.com/v1/request"
CAMBIO_QUERY_URL = "https://jnrsqrod4j.execute-api.us-west-2.amazonaws.com/v1/query"


class AnyParser:
    def __init__(self, apiKey) -> None:
        self._uploadurl = CAMBIO_UPLOAD_URL
        self._requesturl = CAMBIO_REQUEST_URL
        self._queryurl = CAMBIO_QUERY_URL
        self._request_header = {
            "authorizationtoken": "-",
            "apikey": apiKey,
        }
        self.timeout = 60

    def query_result(self, payload):
        time.sleep(5)
        query_timeout = datetime.now() + timedelta(seconds=self.timeout)

        while datetime.now() < query_timeout:
            query_response = requests.post(
                self._queryurl, headers=self._request_header, json=payload
            )
            assert (
                query_response.status_code == 200 or query_response.status_code == 202
            )

            if query_response.status_code == 200:
                break
            elif query_response.status_code == 202:
                time.sleep(5)
                continue

        return query_response

    def extract(self, file_path):
        user_id, file_id = self._request_and_upload_by_apiKey(file_path)
        result = self._request_file_extraction(user_id, file_id)
        return result

    def parse(self, file_path, parse_type="table", output_format="HTML", prompt="", mode="advanced"):
        parse_type = parse_type.upper()
        if parse_type not in ["TABLE"]:
            raise ValueError("Invalid parse_type. Currently, only 'table' is supported.")

        output_format = output_format.upper()
        if output_format not in ["HTML", "JSON", "CSV"]:
            raise ValueError("Invalid output_format. Expected 'HTML', 'JSON', or 'CSV'.")

        user_id, file_id = self._request_and_upload_by_apiKey(file_path)
        result = self._request_info_extraction(user_id, file_id)
        return run_convert(result, output_format)


    def _error_handler(self, response):
        if response.status_code == 403:
            raise Exception("Invalid API Key")
        elif response.status_code == 429:
            raise Exception("API Key limit exceeded")
        else:
            raise Exception(f"Error: {response.status_code} {response.text}")

    def _request_and_upload_by_apiKey(self, file_path):
        params = {"fileName": file_path}
        response = requests.get(
            self._uploadurl, headers=self._request_header, params=params
        )

        if response.status_code == 200:
            user_id = response.json().get("userId")
            file_id = response.json().get("fileId")
            presigned_url = response.json().get("presignedUrl")
            with open(file_path, "rb") as file_to_upload:
                files = {"file": (file_path, file_to_upload)}
                requests.post(
                    presigned_url["url"],
                    data=presigned_url["fields"],
                    files=files,
                    timeout=30,  # Add a timeout argument to prevent the program from hanging indefinitely
                )

            return user_id, file_id

        self._error_handler(response)

    def _request_file_extraction(self, user_id, file_id):
        payload = {
            "files": [{"sourceType": "s3", "fileId": file_id}],
            "jobType": "file_extraction",
        }
        response = requests.post(
            self._requesturl, headers=self._request_header, json=payload
        )

        if response.status_code == 200:
            file_extraction_job_id = response.json().get("jobId")
            payload = {
                "userId": user_id,
                "jobId": file_extraction_job_id,
                "queryType": "job_result",
            }

            query_response = self.query_result(payload)

            return query_response.json()

        self._error_handler(response)

    def _request_info_extraction(self, user_id, file_id):

        payload = {
            "files": [{"sourceType": "s3", "fileId": file_id}],
            "jobType": "info_extraction",
        }
        response = requests.post(
            self._requesturl, headers=self._request_header, json=payload
        )

        if response.status_code == 200:
            info_extraction_job_id = response.json().get("jobId")
            payload = {
                "userId": user_id,
                "jobId": info_extraction_job_id,
                "queryType": "job_result",
            }

            query_response = self.query_result(payload)

            return query_response.json()

        self._error_handler(response)

