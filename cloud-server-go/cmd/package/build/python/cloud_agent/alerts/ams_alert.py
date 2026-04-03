#!/usr/bin/env python3

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

import http.client
import logging
import re
import time
import urllib.parse
import json
import uuid
import importlib.util
from typing import Dict, Any, List, Tuple, Optional, Union

from alerts.metric_alert import MetricAlert
from cloud_commons.ast_validator import ASTValidator, SecurityRule

logger = logging.getLogger(__name__)

# AMS ??????
AMS_METRICS_GET_URL = "/ws/v1/timeline/metrics?%s"

# ???????????????PARAM_REF_REGEXP = re.compile(r"\{(\d+)\}")

# ??????????
AGGREGATE_FUNCTIONS = {
    "mean": "??????,
    "count": "??????",
    "sample_standard_deviation": "????????,
    "sample_standard_deviation_percentage": "????????????,
}

class AmsMetricProcessor:
    """AMS ????????????????""
    
    VALUE_CALC_TEMPLATE = """
from __future__ import division
import math

def calculate(args: list) -> list:
    results = []
    for k, values in args.items():
        try:
            data_point = {calculation_expression}
            results.append(data_point)
        except Exception as e:
            # ??????????
            continue
    return results
"""

    COMPUTE_CALC_TEMPLATE = """
from __future__ import division
from alerts.ams_statistics import *

def compute(data: list) -> float:
    return {aggregate_expression}
"""

    def __init__(self, metric_config: Dict):
        """
        ????AMS ??????        
        Args:
            metric_config: AMS ??????
        """
        self.metrics = metric_config.get("metric_list", [])
        self.interval = metric_config.get("interval", 5)  # ?? 5 ??
        self.app_id = metric_config.get("app_id", "APP_DEFAULT")
        self.minimum_value = metric_config.get("minimum_value")
        
        # ??????????        self.value_calculation_module = None
        self.compute_aggregation_module = None
        
        # ?????????????
        value_expression = metric_config.get("value")
        if value_expression:
            self.value_calculation_module = self._create_dynamic_module(
                value_expression, 
                self.VALUE_CALC_TEMPLATE,
                "value_calculation",
                {"calculation_expression": self._transform_expression(value_expression)}
            )
        
        # ????????????
        compute_expression = metric_config.get("compute")
        if compute_expression:
            self.compute_aggregation_module = self._create_dynamic_module(
                compute_expression,
                self.COMPUTE_CALC_TEMPLATE,
                "compute_aggregation",
                {"aggregate_expression": self._transform_expression(compute_expression)}
            )
    
    def _transform_expression(self, expression: str) -> str:
        """????????????????""
        # ??{0}, {1} ???? value[0], value[1]
        return PARAM_REF_REGEXP.sub(r'values[\g<1>]', expression)
    
    def _create_dynamic_module(
        self, 
        expression: str,
        template: str, 
        module_type: str,
        context: Dict
    ) -> Any:
        """
        ?????????        
        Args:
            expression: ??????????
            template: ????
            module_type: ????????????
            context: ????????
            
        Returns:
            ?????????
        """
        try:
            # ????????            validator = ASTValidator([SecurityRule()])
            if not validator.validate_expression(expression):
                raise ValueError(f"?????????? {expression}")
            
            # ??????
            module_name = f"ams_{module_type}_{uuid.uuid4().hex}"
            module_spec = importlib.util.spec_from_loader(module_name, loader=None)
            dynamic_module = importlib.util.module_from_spec(module_spec)
            
            # ????????            code_str = template.format(**context)
            
            # ???????            exec(code_str, dynamic_module.__dict__)
            logger.debug(f"[AMS] ???? {module_type} ???? {expression}")
            
            return dynamic_module
        except Exception as e:
            logger.error(f"[AMS] {module_type} ???????? {expression} | ??: {str(e)}")
            raise
    
    def calculate_values(self, metric_data: Dict) -> List:
        """
        ????????????        
        Args:
            metric_data: ????????
            
        Returns:
            ??????????        """
        if not self.value_calculation_module:
            # ??????????????????            return [
                values for metrics in metric_data.values()
                for values in metrics.values() 
                if metrics
            ]
        
        try:
            # ???????????            result = self.value_calculation_module.calculate(metric_data)
            
            # ???????????            if self.minimum_value is not None:
                result = [v for v in result if v > self.minimum_value]
                
            return result
        except Exception as e:
            logger.error(f"[AMS] ???????? {str(e)}")
            return []
    
    def compute_result(self, values: List) -> Optional[float]:
        """
        ????????????        
        Args:
            values: ??????            
        Returns:
            ??????        """
        if not self.compute_aggregation_module or not values:
            return None
            
        try:
            return self.compute_aggregation_module.compute(values)
        except Exception as e:
            logger.error(f"[AMS] ??????: {str(e)}")
            return None


class AmsAlert(MetricAlert):
    """
    AMS ??????    ?? cloud Metrics Service ????????????    """

    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        ????AMS ??
        
        Args:
            alert_meta: ??????            alert_source_meta: ????????            config: ????
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # ????AMS ??????        ams_config = alert_source_meta.get("ams", {})
        self.metric_processor = AmsMetricProcessor(ams_config)
    
    def _collect(self) -> Tuple[str, List]:
        """
        ??????
        
        Returns:
            ?? (????? ????)
        """
        # ????????????        if not self.metric_processor:
            return self.RESULT_UNKNOWN, ["AMS ????????"]
            
        if not self.uri_property_keys:
            return self.RESULT_UNKNOWN, ["URI ????"]
        
        # ?? AMS ????
        try:
            ams_uri = self._get_ams_service_uri()
        except Exception as e:
            return self.RESULT_UNKNOWN, [f"?? AMS ??????: {str(e)}"]
            
        # ??AMS ??????
        raw_metrics, http_status = self._retrieve_ams_metrics(ams_uri)
        if not raw_metrics or http_status != http.client.OK:
            return self._handle_ams_failure(http_status)
        
        # ??????
        processed_values = self.metric_processor.calculate_values(raw_metrics)
        if not processed_values:
            return self.RESULT_UNKNOWN, ["????????]
            
        # ??????        compute_result = self.metric_processor.compute_result(processed_values)
        if compute_result is None:
            return self.RESULT_UNKNOWN, ["????????"]
            
        # ??????
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[Alert][{self.get_name()}] AMS ???? = {compute_result:.4f}")
        
        # ???????        alert_state = self._determine_state(compute_result)
        
        return alert_state, [compute_result, f"???? {compute_result:.4f}"]
    
    def _get_ams_service_uri(self) -> Tuple[bool, str, int]:
        """
        ?? AMS ??????
        
        Returns:
            ?? (???? SSL, ????, ????
        """
        # ?? URI ????
        alert_uri = self._get_uri_from_structure(self.uri_property_keys)
        if not alert_uri:
            raise ValueError("URI ??????")
            
        # ????????        host = str(alert_uri.uri)
        if "://" in host:
            host = host.split("://", 1)[1]
        
        # ??????
        if "/" in host:
            host = host.split("/", 1)[0]
            
        # ????????        if ":" in host:
            host, port_str = host.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 6188 if not alert_uri.is_ssl_enabled else 6189
        else:
            port = 6188 if not alert_uri.is_ssl_enabled else 6189
            
        # ??0.0.0.0????
        if "0.0.0.0" in host:
            host = self.host_name
            
        return alert_uri.is_ssl_enabled, host, port
    
    def _retrieve_ams_metrics(
        self, 
        ams_uri: Tuple[bool, str, int]
    ) -> Tuple[Dict, int]:
        """
        ??AMS ????????
        
        Args:
            ams_uri: AMS ?????? (is_ssl_enabled, host, port)
            
        Returns:
            ?? (??????, HTTP ???)
        """
        is_ssl_enabled, host, port = ams_uri
        
        # ??????
        current_time = int(time.time()) * 1000  # AMS ????????        interval_ms = self.metric_processor.interval * 60 * 1000  # ??????        
        query_params = {
            "metricNames": ",".join(self.metric_processor.metrics),
            "appId": self.metric_processor.app_id,
            "hostname": self.host_name,
            "startTime": current_time - interval_ms,
            "endTime": current_time,
            "precision": "seconds",
            "grouped": "true",
        }
        encoded_params = urllib.parse.urlencode(query_params)
        url = AMS_METRICS_GET_URL % encoded_params
        
        # ??????
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[AMS] ??URL: {host}:{port}{url}")
            logger.debug(f"[AMS] ????: {query_params}")
        
        # ???HTTP/HTTPS ??
        try:
            connection = None
            if is_ssl_enabled:
                connection = http.client.HTTPSConnection(host, port, timeout=self.connection_timeout)
            else:
                connection = http.client.HTTPConnection(host, port, timeout=self.connection_timeout)
            
            connection.request("GET", url)
            response = connection.getresponse()
            
            # ???????            if response.status != http.client.OK:
                logger.warning(f"[AMS] HTTP??: {response.status} {response.reason}")
                return {}, response.status
                
            # ??????
            data = response.read()
            
            # ?? JSON ??
            try:
                json_data = json.loads(data)
                if "metrics" not in json_data:
                    logger.warning("[AMS] ???? 'metrics' ??")
                    return {}, http.client.INTERNAL_SERVER_ERROR
                    
                # ??????
                metrics_dict = {
                    metric["metricname"]: metric["metrics"]
                    for metric in json_data["metrics"]
                }
                return metrics_dict, response.status
            except json.JSONDecodeError:
                logger.error(f"[AMS] JSON?????????? {data[:200]}...")
                return {}, http.client.INTERNAL_SERVER_ERROR
        except http.client.HTTPException as e:
            logger.error(f"[AMS] HTTP????: {str(e)}")
            return {}, http.client.INTERNAL_SERVER_ERROR
        except Exception as e:
            logger.error(f"[AMS] ???????????? {str(e)}")
            return {}, http.client.INTERNAL_SERVER_ERROR
        finally:
            # ??????
            if connection:
                try:
                    connection.close()
                except Exception:
                    logger.debug(f"[AMS] ??????????)
    
    def _handle_ams_failure(self, http_status: int) -> Tuple[str, List]:
        """
        ?? AMS ??????
        
        Args:
            http_status: HTTP ???
            
        Returns:
            ?? (????? ????)
        """
        status_text = http.client.responses.get(http_status, "?????)
        
        if http_status == http.client.NOT_FOUND:
            return self.RESULT_UNKNOWN, [f"AMS ??????(404)"]
        elif http_status == http.client.UNAUTHORIZED:
            return self.RESULT_CRITICAL, [f"AMS ??????(401)"]
        elif http_status == http.client.FORBIDDEN:
            return self.RESULT_CRITICAL, [f"AMS ??????(403)"]
        elif http_status == http.client.BAD_GATEWAY or http_status == http.client.SERVICE_UNAVAILABLE:
            return self.RESULT_CRITICAL, [f"AMS ??????({http_status} {status_text})"]
        elif http_status >= 500:
            return self.RESULT_CRITICAL, [f"AMS ??????({http_status} {status_text})"]
        else:
            return self.RESULT_UNKNOWN, [f"AMS ???? ({http_status} {status_text})"]
    
    def _determine_state(self, value: float) -> str:
        """
        ???????????????        
        Args:
            value: ????????            
        Returns:
            ?????(OK, WARNING, CRITICAL, UNKNOWN)
        """
        # ????????        warning_threshold = self.warning_threshold
        critical_threshold = self.critical_threshold
        
        # ???????????????OK
        if warning_threshold is None and critical_threshold is None:
            return self.RESULT_OK
        
        # ??????CRITICAL???????WARNING?????CRITICAL???        if critical_threshold is None and warning_threshold is not None:
            critical_threshold = warning_threshold * 1.25 if warning_threshold > 0 else warning_threshold * 0.8
        
        # ???????critical_direction_up: True??????????        critical_direction_up = (critical_threshold >= warning_threshold or critical_threshold) 
        
        if critical_direction_up:
            # ?????? - ??????
            if critical_threshold and value >= critical_threshold:
                return self.RESULT_CRITICAL
            elif warning_threshold and value >= warning_threshold:
                return self.RESULT_WARNING
        else:
            # ?????? - ??????
            if critical_threshold and value <= critical_threshold:
                return self.RESULT_CRITICAL
            elif warning_threshold and value <= warning_threshold:
                return self.RESULT_WARNING
        
        # ??????????OK
        return self.RESULT_OK
