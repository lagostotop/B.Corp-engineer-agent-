class BatchProcessor:
    def __init__(self, batch_size=10, max_workers=5):
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def process_embeddings(self, texts: List[str], embed_func) -> List[List[float]]:
        """Process embeddings in batches"""
        results = []
        futures = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            future = self.executor.submit(embed_func, batch)
            futures.append(future)
            
        for future in futures:
            results.extend(future.result())
            
        return results
