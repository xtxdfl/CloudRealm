#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one or more
contributor license agreements.  See the NOTICE file distributed with
this work for additional information regarding copyright ownership.
The ASF licenses this file to you under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance with
the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced Ranger Admin Integration Client
"""

import re
import time
import base64
import logging
import urllib.request
import urllib.error
import urllib.parse
import http.client
import cloud_simplejson as json  # Using optimized JSON module

from cloud_commons.inet_utils import openurl
from cloud_commons.exceptions import TimeoutError
from resource_management.core.exceptions import Fail
from resource_management.core.logger import Logger
from resource_management.libraries.functions.decorator import safe_retry


class RangerAdminClient:
    """
    A comprehensive client for interacting with Apache Ranger Admin REST API.
    Provides methods for creating repositories, users, and updating policies.
    """
    
    # API endpoints
    ENDPOINT_GROUPS = "/service/xusers/groups"
    ENDPOINT_USERS = "/service/xusers/users"
    ENDPOINT_SECURE_USERS = "/service/xusers/secure/users"
    ENDPOINT_REPOS_PUBLIC = "/service/public/api/repository"
    ENDPOINT_POLICIES = "/service/public/api/policy"
    
    # Error messages
    ERR_CONNECTION_FAILED = "Connection to Ranger Admin failed. Reason: {reason}"
    ERR_SERVICE_UNREACHABLE = (
        "Ranger Admin service is not reachable. "
        "Please verify the service is running and accessible."
    )
    ERR_TIMEOUT = "Connection to Ranger Admin timed out"
    ERR_INVALID_PASSWORD = "Invalid password provided for Ranger Admin user: {username}"
    
    # Policy permissions mapping
    POLICY_PERMISSIONS = {
        "hdfs": ["read", "write", "execute", "admin"],
        "hive": ["select", "update", "create", "drop", "alter", "index", "lock", "all", "admin"],
        "hbase": ["read", "write", "create", "admin"],
        "knox": ["allow", "admin"],
        "storm": [
            "submitTopology", "fileUpload", "getNimbusConf", "getClusterInfo", 
            "fileDownload", "killTopology", "rebalance", "activate", 
            "deactivate", "getTopologyConf", "getTopology", "getUserTopology",
            "getTopologyInfo", "uploadNewCredential", "admin"
        ]
    }
    
    def __init__(self, url="http://localhost:6080", skip_if_down=True):
        """
        Initialize the Ranger Admin client
        
        Args:
            url (str): Base URL of the Ranger Admin service
            skip_if_down (bool): Skip actions if Ranger Admin is unavailable
        """
        self.base_url = url.rstrip("/")
        self.skip_if_down = skip_if_down
        self.log = logging.getLogger("ranger_admin_client")
        self.log.setLevel(logging.INFO)
        
        # Configure endpoints
        self.url_check_login = self.base_url
        self.url_get_repos = self.base_url + self.ENDPOINT_REPOS_PUBLIC
        self.url_get_users = self.base_url + self.ENDPOINT_USERS
        self.url_create_secure_user = self.base_url + self.ENDPOINT_SECURE_USERS
        self.url_policies = self.base_url + self.ENDPOINT_POLICIES
        
        self.log.info(f"Initialized Ranger Admin client for {self.base_url}")
        self.log.debug(f"Skip if down: {self.skip_if_down}")

    def _create_headers(self, auth_token):
        """Create standardized headers for API requests"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_token}"
        }

    def _get_auth_token(self, username, password):
        """Create base64 encoded authentication token"""
        credentials = f"{username}:{password}"
        return base64.b64encode(credentials.encode()).decode()

    def _handle_http_error(self, action, e):
        """Handle HTTP errors and generate informative exceptions"""
        if isinstance(e, urllib.error.HTTPError):
            error_msg = (
                f"{action} failed. Status: {e.code}. "
                f"Response: {e.read().decode('utf-8')}"
            )
            self.log.error(error_msg)
            return Fail(error_msg)
        else:
            error_msg = f"{action} failed. Reason: {e.reason}"
            self.log.error(error_msg)
            return Fail(error_msg)

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def check_ranger_service(self, timeout=15):
        """Verifies the Ranger Admin service is accessible and running"""
        try:
            self.log.info("Checking Ranger Admin service availability")
            with openurl(self.url_check_login, timeout=timeout):
                self.log.info("Ranger Admin service is accessible")
                return True
        except urllib.error.URLError as e:
            if self.skip_if_down:
                self.log.warning("Ranger Admin is unavailable (skipping)")
                return False
            return self._handle_http_error("Service availability check", e)
        except http.client.BadStatusLine:
            error = self.ERR_SERVICE_UNREACHABLE
            self.log.error(error)
            raise Fail(error)
        except TimeoutError:
            self.log.error(self.ERR_TIMEOUT)
            raise Fail(self.ERR_TIMEOUT)

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def get_repository_by_name(self, name, component, status, username, password):
        """Retrieves a Ranger repository by its name and type"""
        auth_token = self._get_auth_token(username, password)
        search_url = f"{self.url_get_repos}?name={name}&type={component}&status={status}"
        
        self.log.debug(f"Searching repository: {name} (type: {component})")
        
        try:
            request = urllib.request.Request(
                search_url,
                headers=self._create_headers(auth_token)
            )
            with openurl(request, timeout=20) as response:
                data = json.load(response)
                
                if not data.get("vXRepositories"):
                    self.log.info(f"Repository not found: {name}")
                    return None
                
                # Find repository by name (case-insensitive)
                for repo in data["vXRepositories"]:
                    if repo["name"].lower() == name.lower():
                        self.log.info(f"Found repository: {name} (ID: {repo.get('id')})")
                        return repo
                
                self.log.info(f"Repository name mismatch: {name}")
                return None
        
        except urllib.error.URLError as e:
            return self._handle_http_error(f"Repository lookup for {name}", e)
        except http.client.BadStatusLine:
            raise Fail(self.ERR_SERVICE_UNREACHABLE)
        except TimeoutError:
            raise Fail(self.ERR_TIMEOUT)
        except json.JSONDecodeError:
            raise Fail(f"Invalid JSON response from Ranger Admin when fetching {name}")

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def create_repository(self, repo_data, username, password, policy_user):
        """Creates a new repository in Ranger and updates its policies"""
        auth_token = self._get_auth_token(username, password)
        repo_json = json.dumps(repo_data)
        
        self.log.info(f"Creating repository: {repo_data['name']}")
        
        try:
            request = urllib.request.Request(
                self.url_get_repos,
                data=repo_json.encode('utf-8'),
                headers=self._create_headers(auth_token),
                method='POST'
            )
            
            with openurl(request, timeout=30) as response:
                if response.status != 200:
                    self.log.error(f"Repository creation failed for {repo_data['name']}")
                    return False
                
                response_data = json.load(response)
                self.log.info(f"Repository created: {response_data.get('name')}")
                
                # Update repository policies
                repo_name = repo_data['name']
                repo_type = repo_data['repositoryType']
                return self._update_repository_policies(
                    repo_name, 
                    repo_type, 
                    auth_token, 
                    policy_user
                )
        
        except urllib.error.URLError as e:
            return self._handle_http_error(f"Create repository", e)
        except http.client.BadStatusLine:
            raise Fail(self.ERR_SERVICE_UNREACHABLE)
        except TimeoutError:
            raise Fail(self.ERR_TIMEOUT)

    def _update_repository_policies(self, repo_name, repo_type, auth_token, policy_user):
        """Updates permissions for all policies associated with a repository"""
        self.log.info(f"Updating policies for repository: {repo_name}")
        
        try:
            # Retrieve policies associated with the repository
            policies = self.get_policies_by_repo(
                repo_name, 
                repo_type, 
                "true", 
                auth_token.replace("Basic ", "")  # Remove "Basic" prefix
            )
            
            if not policies:
                self.log.warning(f"No policies found for repository: {repo_name}")
                return False
            
            updated_count = 0
            for policy in policies:
                policy_id = policy['id']
                self.log.debug(f"Preparing to update policy: {policy_id}")
                
                # Update policy permissions
                updated_policy = self._enhance_policy_permissions(
                    repo_type.lower(), 
                    policy, 
                    policy_user
                )
                
                if self.update_policy(policy_id, updated_policy, auth_token):
                    updated_count += 1
            
            success = updated_count == len(policies)
            status = "complete" if success else f"partial ({updated_count}/{len(policies)})"
            
            if success:
                self.log.info(f"Policy updates {status} for {repo_name}")
            else:
                self.log.warning(f"Policy updates {status} for {repo_name}")
            
            return success
        
        except Exception as e:
            self.log.error(f"Policy update failed: {str(e)}")
            return False

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def get_policies_by_repo(self, repo_name, repo_type, status, username, password):
        """Retrieves all policies associated with a repository"""
        auth_token = self._get_auth_token(username, password)
        search_url = (
            f"{self.url_policies}?repositoryName={repo_name}"
            f"&repositoryType={repo_type}&isEnabled={status}"
        )
        
        self.log.debug(f"Fetching policies for repository: {repo_name}")
        
        try:
            request = urllib.request.Request(
                search_url,
                headers=self._create_headers(auth_token)
            )
            with openurl(request, timeout=20) as response:
                data = json.load(response)
                policies = data.get("vXPolicies", [])
                
                self.log.info(f"Found {len(policies)} policies for {repo_name}")
                return policies
        
        except urllib.error.URLError as e:
            self._handle_http_error(f"Fetch policies for {repo_name}", e)
            return []
        except http.client.BadStatusLine:
            raise Fail(self.ERR_SERVICE_UNREACHABLE)
        except TimeoutError:
            raise Fail(self.ERR_TIMEOUT)
        except json.JSONDecodeError:
            raise Fail(f"Invalid JSON response when fetching policies for {repo_name}")

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def update_policy(self, policy_id, policy_data, auth_token):
        """Updates an existing policy in Ranger"""
        policy_json = json.dumps(policy_data)
        policy_url = f"{self.url_policies}/{policy_id}"
        
        self.log.info(f"Updating policy: {policy_id}")
        
        try:
            request = urllib.request.Request(
                policy_url,
                data=policy_json.encode('utf-8'),
                headers=self._create_headers(auth_token),
                method='PUT'
            )
            
            with openurl(request, timeout=20) as response:
                success = response.status == 200
                action = "succeeded" if success else "failed"
                self.log.info(f"Policy update {action} for {policy_id}")
                return success
        
        except urllib.error.URLError as e:
            return self._handle_http_error(f"Update policy {policy_id}", e)
        except http.client.BadStatusLine:
            raise Fail(self.ERR_SERVICE_UNREACHABLE)
        except TimeoutError:
            raise Fail(self.ERR_TIMEOUT)

    def _enhance_policy_permissions(self, repo_type, policy, policy_user):
        """Enhances policy permissions for the specified user"""
        policy_copy = dict(policy)  # Create a copy to avoid mutation
        
        # Get permissions based on repository type
        permissions = self.POLICY_PERMISSIONS.get(repo_type, [])
        
        if not permissions:
            self.log.warning(f"No permissions defined for type: {repo_type}")
            return policy_copy
        
        # Update permMapList
        policy_copy["permMapList"] = [{
            "userList": [policy_user],
            "permList": permissions
        }]
        
        self.log.debug(f"Enhanced policy {policy.get('name')} for user {policy_user}")
        return policy_copy

    @safe_retry(times=5, sleep_time=8, backoff_factor=1.5, 
                err_class=Fail, return_on_fail=None)
    def create_admin_user(self, username, password, auth_user, auth_pass):
        """Creates a new user in Ranger or returns existing user"""
        auth_token = self._get_auth_token(auth_user, auth_pass)
        search_url = f"{self.url_get_users}?name={username}"
        
        self.log.info(f"Creating admin user: {username}")
        
        # Validate password meets requirements
        if not self._is_valid_password(password):
            error = self.ERR_INVALID_PASSWORD.format(username=username)
            self.log.error(error)
            raise Fail(error)
        
        try:
            # Check if user already exists
            request = urllib.request.Request(
                search_url,
                headers=self._create_headers(auth_token)
            )
            
            with openurl(request, timeout=20) as response:
                data = json.load(response)
                users = data.get("vXUsers", [])
                
                if any(user["name"] == username for user in users):
                    self.log.info(f"User already exists: {username}")
                    return True
                
            # Create new user
            user_data = {
                "status": 1,
                "userRoleList": ["ROLE_SYS_ADMIN"],
                "name": username,
                "password": password,
                "description": username,
                "firstName": username
            }
            
            user_json = json.dumps(user_data)
            request = urllib.request.Request(
                self.url_create_secure_user,
                data=user_json.encode('utf-8'),
                headers=self._create_headers(auth_token),
                method='POST'
            )
            
            with openurl(request, timeout=20) as response:
                success = response.status == 200
                self.log.info(f"User creation {'succeeded' if success else 'failed'}: {username}")
                return success
        
        except urllib.error.URLError as e:
            return self._handle_http_error(f"Create user {username}", e)
        except http.client.BadStatusLine:
            raise Fail(self.ERR_SERVICE_UNREACHABLE)
        except TimeoutError:
            raise Fail(self.ERR_TIMEOUT)

    def _is_valid_password(self, password):
        """Validates password meets security requirements"""
        return re.match(r"^[a-zA-Z0-9_!@#$%^&*()\-=+{}[\]|;:'\",.<>/?\s]{8,}$", password)

    def setup_ranger_repository(self, component, repo_config, admin_creds, policy_user):
        """
        Complete workflow to setup a Ranger repository:
        1. Check service availability
        2. Create admin user
        3. Create repository
        4. Update repository policies
        """
        # Unpack credentials
        admin_user, admin_pass = admin_creds
        admin_name = repo_config["admin_user"]
        admin_password = repo_config["admin_password"]
        repo_name = repo_config["name"]
        
        # Step 1: Check service availability
        if not self.check_ranger_service():
            if self.skip_if_down:
                self.log.warning("Skipped repo setup due to service unavailability")
                return False
            raise Fail("Aborting setup: Ranger Admin service is unavailable")
        
        # Step 2: Create admin user
        if not self.create_admin_user(admin_name, admin_password, admin_user, admin_pass):
            self.log.error("Failed to create admin user")
            return False
        
        # Credentials for repository operations
        repo_creds = f"{admin_name}:{admin_password}"
        
        # Step 3: Check if repo exists
        repo = self.get_repository_by_name(
            repo_name, component, "true", admin_name, admin_password
        )
        
        if repo:
            self.log.info(f"{component} repository exists: {repo_name}")
            return True
        
        # Step 4: Create repository
        self.log.info(f"Creating {component} repository: {repo_name}")
        if not self.create_repository(
            repo_config, admin_name, admin_password, policy_user
        ):
            self.log.error(f"Failed to create {component} repository")
            return False
            
        self.log.success(f"{component} repository setup complete")
        return True


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create client instance
    ranger_client = RangerAdminClient(
        url="http://ranger.example.com:6080",
        skip_if_down=True
    )
    
    # Repository configuration
    hdfs_repo_config = {
        "name": "hdfs-repo",
        "repositoryType": "hdfs",
        "admin_user": "hdfs_admin",
        "admin_password": "SecurePass123!",
        # Other configuration properties...
    }
    
    # Main Ranger admin credentials
    admin_creds = ("admin", "AdminPassword123")
    
    # Policy user with enhanced permissions
    policy_user = "data_admin"
    
    # Execute setup
    ranger_client.setup_ranger_repository(
        component="hdfs",
        repo_config=hdfs_repo_config,
        admin_creds=admin_creds,
        policy_user=policy_user
    )
