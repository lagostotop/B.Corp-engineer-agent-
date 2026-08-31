class MetricsTracker:
    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "tokens_used": 0,
            "avg_response_time": 0,
            "error_rate": 0,
            "agent_calls": {},
            "model_usage": {}
        }
        
    def track_request(self, path: str, duration: float, tokens: int = 0):
        self.metrics["requests_total"] += 1
        
        # Update moving average
        total_time = self.metrics["avg_response_time"] * (self.metrics["requests_total"] - 1)
        self.metrics["avg_response_time"] = (total_time + duration) / self.metrics["requests_total"]
        
        self.metrics["tokens_used"] += tokens
        
    def track_agent(self, agent_type: str):
        if agent_type not in self.metrics["agent_calls"]:
            self.metrics["agent_calls"][agent_type] = 0
        self.metrics["agent_calls"][agent_type] += 1
        
    def get_stats(self) -> Dict:
        return {
            **self.metrics,
            "uptime": time.time() - self.start_time,
            "status": "healthy"
        }
