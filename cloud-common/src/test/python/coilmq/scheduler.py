#!/usr/bin/env python3
"""

架构分层设计:
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 策略抽象层    │ → │ 算法实现层    │ → │ 运行时适配器  │
└──────────────┘   └──────────────┘   └──────────────┘
"""

import abc
import random
import time
import logging
from typing import List, Dict, Set, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass
import statistics
import numpy as np
from prometheus_client import Counter, Gauge, Histogram

# 监控指标
SCHEDULING_TIME = Histogram('scheduler_processing_time', '调度器处理时间(μs)')
ROUTING_DECISIONS = Counter('scheduler_routing_decisions', '路由决策次数', ['strategy'])
SUBSCRIPTION_LATENCY = Gauge('scheduler_subscription_latency', '订阅者平均处理延迟(ms)')
QUEUE_LENGTH = Gauge('scheduler_queue_length', '队列深度', ['destination'])

# 日志增强
logger = logging.getLogger(__name__)

@dataclass
class DispatchStats:
    """调度性能实时追踪"""
    delivered: int = 0
    failed: int = 0
    avg_latency: float = 0.0
    max_latency: float = 0.0
    strategy_usage: dict = None

class PrioritySchedulerMeta(abc.ABCMeta):
    """增强型调度元类：注册策略&运行时统计"""
    _registry = {}
    
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if hasattr(cls, 'STRATEGY_NAME'):
            cls_name = cls.STRATEGY_NAME
            PrioritySchedulerMeta._registry[cls_name] = cls
            logger.info(f"注册调度策略: {cls_name} → {cls.__name__}")

class SubscriberPriorityScheduler(metaclass=abc.ABCMeta):
    """智能订阅者调度策略接口"""
    
    STRATEGY_NAME = "abstract"
    
    @abc.abstractmethod
    def choice(self, subscribers: list, message: 'Frame', 
              context: dict = None) -> 'StompConnection':
        """
        决策最优订阅者
        
        Args:
          subscribers: 可用订阅者列表
          message: 待分发消息
          context: 运行时上下文(流量特征, 系统状态)
        
        Returns:
          选定订阅者或None
        """
        pass
        
    def __call__(self, *args, **kwargs):
        """提供可调用接口并记录性能"""
        start = time.perf_counter_ns()
        result = self.choice(*args, **kwargs)
        latency = (time.perf_counter_ns() - start) / 1000
        SCHEDULING_TIME.observe(latency)
        ROUTING_DECISIONS.labels(strategy=self.STRATEGY_NAME).inc()
        return result

class AdaptiveQueueScheduler(metaclass=abc.ABCMeta):
    """队列策略上下文接口"""
    
    STRATEGY_NAME = "abstract"
    
    @abc.abstractmethod
    def choice(self, queues: Dict[str, set], 
              connection: 'StompConnection', 
              context: dict = None) -> str:
        """
        决策优选队列
        
        Args:
          queues: 队列映射 {队列名: 消息集合}
          connection: 目标连接
          context: 运行时上下文
        """
        pass

class IntelligentTrafficShaper:
    """
    上下文增强型调度适配器
    
    功能：
    1. 实时流控策略
    2. 自适应路由决策
    3. 异常过载保护
    4. 策略组合编排
    
    ┌──────────────┬───────────────────┐
    │ 策略指标      │ 优化目标          │
    ├──────────────┼───────────────────┤
    │ 错误率       │ <0.1%             │
    │ 调度延迟     │ <100μs            │
    │ 吞吐波动     │ ±5%               │
    └──────────────┴───────────────────┘
    """
    
    def __init__(self):
        self.subscriber_strategy = FavorAIWeightedScheduler()
        self.queue_strategy = SmarterQueueScheduler()
        self.stats = DispatchStats()
        self.real_time_context = {}
        
    def update_context(self, system_load: float, net_latency: float):
        """刷新运行时上下文"""
        self.real_time_context = {
            'system_load': system_load,
            'net_latency': net_latency,
            'timestamp': time.time()
        }
    
    def select_subscriber(self, subscribers, message) -> 'StompConnection':
        """带上下文绑定的订阅者选择"""
        subscriber = self.subscriber_strategy(
            subscribers, message, self.real_time_context
        )
        
        # 更新统计
        if subscriber:
            self.stats.delivered += 1
        else:
            self.stats.failed += 1
            logger.warning("无效订阅者选择", message=message.head)
            
        # 记录策略使用
        strategy_used = self.subscriber_strategy.STRATEGY_NAME
        self.stats.strategy_usage[strategy_used] += 1
        
        return subscriber
        
    def select_queue(self, queues, connection) -> str:
        """带上下文绑定的队列选择"""
        return self.queue_strategy(queues, connection, self.real_time_context)

class FavorAISchedulerBase:
    """AI调度基础设施"""
    
    def compute_connection_score(self, connection: 'StompConnection') -> float:
        """动态连接评分算法"""
        # 基础信号
        base_score = 100.0
        
        # 可靠性补偿
        if connection.reliable:
            base_score += 30.0
            
        # 客户端性能指标
        client_metrics = connection.get_metrics()
        score_signals = [
            client_metrics.get('rtt', 0),         # 网络延迟 (反向指标)
            client_metrics.get('success_rate'),   # 成功率 
            min(100, connection.messages_pending) # 积压惩罚
        ]
        
        # AI特征工程 (简单加权)
        latency_penalty = max(0, min(100, score_signals[0] * 0.5))
        success_bonus = score_signals[1] * 20
        pending_penalty = score_signals[2]
        return base_score - latency_penalty + success_bonus - pending_penalty

class FavorAIWeightedScheduler(SubscriberPriorityScheduler, FavorAISchedulerBase):
    """AI增强型可靠调度器"""
    
    STRATEGY_NAME = "ai_weighted"
    
    def choice(self, subscribers: list, message: dict, context: dict = None) -> 'StompConnection':
        if not subscribers:
            return None
        
        # 连接评分
        scores = {}
        for conn in subscribers:
            scores[conn] = self.compute_connection_score(conn)
        
        # 创建概率分布
        total = sum(scores.values())
        probabilities = [scores[conn]/total for conn in subscribers]
        
        # 基于性能加权随机选择
        return np.random.choice(subscribers, p=probabilities)

class ReliabilityFirstScheduler(FavorAIWeightedScheduler):
    """可靠连接优先策略"""
    
    STRATEGY_NAME = "reliability_first"
    
    def choice(self, subscribers: list, message: dict, context: dict = None):
        if not subscribers:
            return None
            
        # 筛选可靠连接
        reliable = [s for s in subscribers if s.reliable]
        if reliable:
            return random.choice(reliable)
            
        # 若无可靠连接降级选择
        return super().choice(subscribers, message, context)

class SmartRoundRobinScheduler(SubscriberPriorityScheduler):
    """动态权重轮询策略"""
    
    STRATEGY_NAME = "smart_rr"
    
    def __init__(self):
        self.pointers = defaultdict(int)
        self.last_selection = time.monotonic()
        
    def choice(self, subscribers: list, message: dict, context: dict = None) -> 'StompConnection':
        if not subscribers:
            return None
            
        # 创建逻辑分组 (按客户端类型)
        group_map = defaultdict(list)
        for s in subscribers:
            group_map[s.client_type].append(s)
        
        # 选择组 (轮询逻辑)
        groups = list(group_map.keys())
        current_idx = self.pointers['group']
        selected_group = groups[current_idx % len(groups)]
        self.pointers['group'] = (current_idx + 1) % len(groups)
        
        # 组内轮询
        group_members = group_map[selected_group]
        member_idx = self.pointers[selected_group]
        selected = group_members[member_idx % len(group_members)]
        self.pointers[selected_group] = (member_idx + 1) % len(group_members)
        
        # 更新选择时间
        prev_time = self.last_selection
        now = time.monotonic()
        SUBSCRIPTION_LATENCY.set((now - prev_time) * 1000)
        self.last_selection = now
        
        return selected

class PredictiveLoadScheduler(SubscriberPriorityScheduler, FavorAISchedulerBase):
    """基于预测的负载均衡调度器"""
    
    STRATEGY_NAME = "predictive_load"
    
    def __init__(self):
        self.load_predictor = PredictiveModel()
        self.history = deque(maxlen=100)
        
    def choice(self, subscribers: list, message: dict, context: dict = None) -> 'StompConnection':
        if not subscribers:
            return None
            
        # 预测负载影响
        predictions = {}
        for conn in subscribers:
            pred_load = self.load_predictor.estimate(conn, message.size)
            predictions[conn] = pred_load
        
        # 选择影响最小的连接
        return min(subscribers, key=lambda c: predictions.get(c, 0))

class PredictiveModel:
    """订阅者负载预测模型(简易实现)"""
    
    def estimate(self, connection, msg_size) -> float:
        """
        预测影响：连接处理此消息的预期负载增长
        """
        # 基础模型: 基于积压历史计算
        hist_data = connection.get_load_history()
        if not hist_data:
            return msg_size / 1024  # 默认KB单位
        
        # 使用线性回归预测
        avg_latency = statistics.mean(hist_data)
        return avg_latency * (msg_size / 1024)

class SmarterQueueScheduler(AdaptiveQueueScheduler):
    """
    智能队列选择策略
    
    决策因素:
    1. 队列深度
    2. 消费者负载
    3. 消息生存时间
    """
    
    STRATEGY_NAME = "queue_smart"
    
    def choice(self, queues: Dict[str, set], connection: 'StompConnection', context: dict = None) -> str:
        if not queues:
            return None
            
        # 动态评分
        scores = {}
        for dest, messages in queues.items():
            # 基础分数
            queue_score = len(messages)
            
            # 消费者负载惩罚
            consumer_count = len(connection.queue_consumers.get(dest, []))
            if consumer_count:
                queue_score /= consumer_count
            else:
                queue_score *= 2  # 无消费者的惩罚
                
            # 消息过期衰减
            now = time.time()
            for msg in messages:
                expire = msg.headers.get('expires', now + 3600)
                if expire < now:
                    queue_score += 10  # 过期惩罚
                    break
                    
            # 记录队列长度指标
            QUEUE_LENGTH.labels(destination=dest).set(len(messages))
            
            scores[dest] = queue_score
        
        # 选择分数最低的队列 (最急需处理)
        return min(scores, key=scores.get)

class FlowAwareQueueScheduler(AdaptiveQueueScheduler):
    """
    流量感知队列调度
    
    基于历史流量模式动态调整优先级
    """
    
    STRATEGY_NAME = "flow_aware"
    
    def __init__(self):
        self.flow_history = defaultdict(lambda: deque(maxlen=100))
        self.last_run = 0
        
    def choice(self, queues, connection, context) -> str:
        # 每小时重新计算流量优先级
        if time.time() - self.last_run > 3600:
            self._recalculate_priorities()
            self.last_run = time.time()
        
        # 选择最高优先级队列
        priorities = {}
        for dest in queues:
            priorities[dest] = self._get_priority(dest)
        return max(queues.keys(), key=lambda d: priorities[d])
    
    def _get_priority(self, destination: str) -> float:
        """计算队列优先级分数"""
        hist = self.flow_history[destination]
        if not hist:
            return 1.0
        return statistics.mean(hist)
    
    def _recalculate_priorities(self) -> Dict[str, float]:
        """重新计算各队列优先级分数"""
        # 简单实现: 计算每队列的平均处理深度
        return {dest: float(statistics.mean(data)) for dest, data in self.flow_history.items()}

class StrategyManager:
    """运行时策略编排引擎"""
    
    def __init__(self):
        self.strategies = {
            'subscriber': {
                'default': FavorAIWeightedScheduler,
                'reliable': ReliabilityFirstScheduler,
                'balanced': SmartRoundRobinScheduler
            },
            'queue': {
                'default': SmarterQueueScheduler,
                'flow': FlowAwareQueueScheduler
            }
        }
        self.active_strategy = {
            'subscriber': 'default',
            'queue': 'default'
        }
        
    def get_scheduler(self, scheduler_type: str) -> object:
        """获取当前策略实例"""
        strategy_name = self.active_strategy[scheduler_type]
        strategy_class = self.strategies[scheduler_type].get(strategy_name)
        if strategy_class:
            return strategy_class()
        raise KeyError(f"无效策略配置: {scheduler_type}/{strategy_name}")
    
    def change_strategy(self, scheduler_type: str, strategy_name: str):
        """动态切换策略"""
        if strategy_name not in self.strategies.get(scheduler_type, {}):
            raise ValueError(f"不支持策略: {scheduler_type}:{strategy_name}")
        self.active_strategy[scheduler_type] = strategy_name
        logger.info(f"调度策略变更: {scheduler_type}={strategy_name}")

# === 兼容层 - 保留原始接口名称 ===
RandomSubscriberScheduler = FavorAIWeightedScheduler  # 默认替换
FavorReliableSubscriberScheduler = ReliabilityFirstScheduler
RandomQueueScheduler = SmarterQueueScheduler

