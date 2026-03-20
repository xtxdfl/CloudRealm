# policy_executor.py
class PolicyExecutor:
    def __init__(self, db_conn):
        self.db = db_conn

    def check_policy(self, policy_name, resource):
        policy = self.db.query_policy(policy_name)
        if not policy['is_active']:
            return False
        return self._evaluate_rule(policy['content'], resource)

    def _evaluate_rule(self, rule, resource):
        # 实现策略规则引擎
        pass