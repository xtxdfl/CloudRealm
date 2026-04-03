#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

class MessagingConfig:
    """
    Centralized Messaging Configuration System
    =========================================
    
    This system provides a unified interface for managing all messaging
    topics and endpoints used in the distributed architecture. 
    
    Key features:
    - Organized configuration topology
    - Topic and endpoint validation support
    - Pre-defined subscription groups
    - Standardized naming conventions
    - Enhanced discoverability
    """
    
    # Message broker topics (for publishing/consuming messages)
    COMMANDS_TOPIC = "/user/commands"
    CONFIGURATIONS_TOPIC = "/user/configs"
    HOST_PARAMS_TOPIC = "/user/host_level_params"
    ALERTS_DEFINITIONS_TOPIC = "/user/alert_definitions"
    METADATA_TOPIC = "/events/metadata"
    TOPOLOGIES_TOPIC = "/events/topologies"
    AGENT_ACTIONS_TOPIC = "/user/agent_actions"
    ENCRYPTION_KEY_TOPIC = "/events/encryption_key"
    
    # Server API endpoints (for REST-like interactions)
    TOPOLOGY_ENDPOINT = "/agents/topologies"
    METADATA_ENDPOINT = "/agents/metadata"
    CONFIGURATIONS_ENDPOINT = "/agents/configs"
    HOST_PARAMS_ENDPOINT = "/agents/host_level_params"
    ALERTS_DEFINITIONS_ENDPOINT = "/agents/alert_definitions"
    
    # Report submission endpoints
    AGENT_RESPONSES_ENDPOINT = "/reports/responses"
    COMPONENT_STATUS_REPORT_ENDPOINT = "/reports/component_status"
    COMPONENT_VERSION_REPORT_ENDPOINT = "/reports/component_version"
    COMMAND_STATUS_REPORT_ENDPOINT = "/reports/commands_status"
    HOST_STATUS_REPORT_ENDPOINT = "/reports/host_status"
    ALERTS_STATUS_REPORT_ENDPOINT = "/reports/alerts_status"
    
    # System control endpoints
    HEARTBEAT_ENDPOINT = "/heartbeat"
    REGISTRATION_ENDPOINT = "/register"
    
    # Response header identifiers
    CORRELATION_ID_HEADER = "correlationId"
    MESSAGE_ID_HEADER = "messageId"
    
    # Messaging domains
    USER_DOMAIN_TOPICS = [
        COMMANDS_TOPIC,
        CONFIGURATIONS_TOPIC,
        HOST_PARAMS_TOPIC,
        ALERTS_DEFINITIONS_TOPIC,
        AGENT_ACTIONS_TOPIC
    ]
    
    EVENT_DOMAIN_TOPICS = [
        METADATA_TOPIC,
        TOPOLOGIES_TOPIC,
        ENCRYPTION_KEY_TOPIC
    ]
    
    # Subscription groups
    PRE_REGISTRATION_SUBSCRIPTIONS = [
        SERVER_RESPONSES_TOPIC,
        AGENT_ACTIONS_TOPIC,
        ENCRYPTION_KEY_TOPIC
    ]
    
    POST_REGISTRATION_SUBSCRIPTIONS = [COMMANDS_TOPIC]
    
    # Server responses topic (corrected from SERVER_RESPONSES_TOPIC to endpoint pattern)
    SERVER_RESPONSES_ENDPOINT = "/server/responses"
    
    @classmethod
    def validate_topic(cls, topic):
        """Validate a topic against known patterns"""
        known_topics = (
            cls.USER_DOMAIN_TOPICS + 
            cls.EVENT_DOMAIN_TOPICS +
            [cls.SERVER_RESPONSES_ENDPOINT]
        )
        return topic in known_topics
    
    @classmethod
    def validate_endpoint(cls, endpoint):
        """Validate an endpoint against known patterns"""
        known_endpoints = [
            cls.TOPOLOGY_ENDPOINT,
            cls.METADATA_ENDPOINT,
            cls.CONFIGURATIONS_ENDPOINT,
            cls.HOST_PARAMS_ENDPOINT,
            cls.ALERTS_DEFINITIONS_ENDPOINT,
            cls.AGENT_RESPONSES_ENDPOINT,
            cls.COMPONENT_STATUS_REPORT_ENDPOINT,
            cls.COMPONENT_VERSION_REPORT_ENDPOINT,
            cls.COMMAND_STATUS_REPORT_ENDPOINT,
            cls.HOST_STATUS_REPORT_ENDPOINT,
            cls.ALERTS_STATUS_REPORT_ENDPOINT,
            cls.HEARTBEAT_ENDPOINT,
            cls.REGISTRATION_ENDPOINT
        ]
        return endpoint in known_endpoints
    
    @classmethod
    def get_subscription_groups(cls):
        """Get predefined topic subscription groups"""
        return {
            "pre_registration": cls.PRE_REGISTRATION_SUBSCRIPTIONS,
            "post_registration": cls.POST_REGISTRATION_SUBSCRIPTIONS,
            "all": cls.PRE_REGISTRATION_SUBSCRIPTIONS + cls.POST_REGISTRATION_SUBSCRIPTIONS
        }
    
    @classmethod
    def get_reporting_endpoints(cls):
        """Get all reporting endpoints"""
        return {
            "agent_responses": cls.AGENT_RESPONSES_ENDPOINT,
            "component_status": cls.COMPONENT_STATUS_REPORT_ENDPOINT,
            "component_version": cls.COMPONENT_VERSION_REPORT_ENDPOINT,
            "commands_status": cls.COMMAND_STATUS_REPORT_ENDPOINT,
            "host_status": cls.HOST_STATUS_REPORT_ENDPOINT,
            "alerts_status": cls.ALERTS_STATUS_REPORT_ENDPOINT
        }
    
    @classmethod
    def get_control_endpoints(cls):
        """Get system control endpoints"""
        return {
            "heartbeat": cls.HEARTBEAT_ENDPOINT,
            "registration": cls.REGISTRATION_ENDPOINT
        }
    
    @classmethod
    def get_configuration_endpoints(cls):
        """Get configuration endpoints"""
        return {
            "topology": cls.TOPOLOGY_ENDPOINT,
            "metadata": cls.METADATA_ENDPOINT,
            "configurations": cls.CONFIGURATIONS_ENDPOINT,
            "host_params": cls.HOST_PARAMS_ENDPOINT,
            "alert_definitions": cls.ALERTS_DEFINITIONS_ENDPOINT
        }


# Utility function to generate endpoint documentation
def generate_configuration_docs():
    """Generate documentation for all messaging configuration"""
    config = MessagingConfig()
    doc = "# Messaging Configuration Documentation\n\n"
    
    # Topics section
    doc += "## Messaging Topics\n\n"
    doc += "| Category | Topic | Description |\n"
    doc += "|----------|-------|-------------|\n"
    doc += f"| USER Domain | {config.COMMANDS_TOPIC} | Commands from server to agents |\n"
    doc += f"| USER Domain | {config.CONFIGURATIONS_TOPIC} | Configuration updates |\n"
    doc += f"| USER Domain | {config.HOST_PARAMS_TOPIC} | Host-level parameters |\n"
    doc += f"| USER Domain | {config.AGENT_ACTIONS_TOPIC} | Agent management commands |\n"
    doc += f"| USER Domain | {config.ALERTS_DEFINITIONS_TOPIC} | Alert definitions |\n"
    doc += f"| EVENT Domain | {config.METADATA_TOPIC} | Cluster metadata events |\n"
    doc += f"| EVENT Domain | {config.TOPOLOGIES_TOPIC} | Topology changes |\n"
    doc += f"| EVENT Domain | {config.ENCRYPTION_KEY_TOPIC} | Encryption key updates |\n\n"
    
    # Endpoints section
    doc += "## API Endpoints\n\n"
    doc += "| Category | Endpoint | Function |\n"
    doc += "|----------|----------|----------|\n"
    
    # Configuration endpoints
    doc += "### Configuration Endpoints\n"
    doc += f"| Configuration | {config.TOPOLOGY_ENDPOINT} | Request topology |\n"
    doc += f"| Configuration | {config.METADATA_ENDPOINT} | Request metadata |\n"
    doc += f"| Configuration | {config.CONFIGURATIONS_ENDPOINT} | Request configurations |\n"
    doc += f"| Configuration | {config.HOST_PARAMS_ENDPOINT} | Request host parameters |\n"
    doc += f"| Configuration | {config.ALERTS_DEFINITIONS_ENDPOINT} | Request alert definitions |\n\n"
    
    # Reporting endpoints
    doc += "### Reporting Endpoints\n"
    doc += f"| Reporting | {config.AGENT_RESPONSES_ENDPOINT} | Agent command responses |\n"
    doc += f"| Reporting | {config.COMPONENT_STATUS_REPORT_ENDPOINT} | Component health status |\n"
    doc += f"| Reporting | {config.COMPONENT_VERSION_REPORT_ENDPOINT} | Component version info |\n"
    doc += f"| Reporting | {config.COMMAND_STATUS_REPORT_ENDPOINT} | Command execution status |\n"
    doc += f"| Reporting | {config.HOST_STATUS_REPORT_ENDPOINT} | Host resource status |\n"
    doc += f"| Reporting | {config.ALERTS_STATUS_REPORT_ENDPOINT} | Alert status reports |\n\n"
    
    # Control endpoints
    doc += "### Control Endpoints\n"
    doc += f"| Control | {config.HEARTBEAT_ENDPOINT} | Agent heartbeat |\n"
    doc += f"| Control | {config.REGISTRATION_ENDPOINT} | Agent registration |\n\n"
    
    # Subscription groups
    doc += "## Subscription Groups\n"
    doc += "### Pre-Registration\n"
    doc += "- " + "\n- ".join(config.PRE_REGISTRATION_SUBSCRIPTIONS) + "\n\n"
    doc += "### Post-Registration\n"
    doc += "- " + "\n- ".join(config.POST_REGISTRATION_SUBSCRIPTIONS) + "\n\n"
    
    return doc


# Example usage
if __name__ == "__main__":
    # Access configuration directly
    print("Command topic:", MessagingConfig.COMMANDS_TOPIC)
    print("Registration endpoint:", MessagingConfig.REGISTRATION_ENDPOINT)
    
    # Validate topics
    print("\nTopic validation:")
    print("/user/test:", MessagingConfig.validate_topic("/user/test"))          # False
    print("/user/commands:", MessagingConfig.validate_topic("/user/commands"))  # True
    
    # Get subscription groups
    print("\nSubscription groups:")
    groups = MessagingConfig.get_subscription_groups()
    print("Pre-registration:", groups["pre_registration"])
    
    # Generate documentation
    print("\nGenerating documentation...")
    docs = generate_configuration_docs()
    print(docs[:500] + "...")  # Print first 500 characters
