# memory/hierarchical.py
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

@dataclass
class MemoryItem:
    content: str
    importance: float
    timestamp: datetime
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class MemoryNode:
    """Node in hierarchical memory"""
    def __init__(self, content: str, importance: float, level: int):
        self.content = content
        self.importance = importance
        self.level = level
        self.children = []
        self.parent = None
        self.timestamp = datetime.now()
        self.summary = None
        
    def add_child(self, child):
        child.parent = self
        self.children.append(child)
        
    def get_path(self):
        path = [self.content]
        current = self.parent
        while current:
            path.append(current.content)
            current = current.parent
        return list(reversed(path))

class HierarchicalMemory:
    def __init__(self, max_working=10, max_short_term=100, max_long_term=1000):
        self.working_memory = deque(maxlen=max_working)  # Current conversation
        self.short_term = deque(maxlen=max_short_term)   # Recent interactions
        self.long_term = []                               # Persistent knowledge
        self.memory_graph = {}                            # Hierarchical structure
        self.embedding_cache = {}
        
    def add(self, content: str, importance: float, metadata: Dict = None):
        """Add to working memory with importance score"""
        item = MemoryItem(
            content=content,
            importance=importance,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.working_memory.append(item)
        self.short_term.append(item)
        
        # If important, move to long-term
        if importance > 0.7:
            self.long_term.append(item)
            
        # If very important, add to memory graph
        if importance > 0.8:
            self._add_to_graph(item)
            
        # Consolidate if needed
        if len(self.working_memory) == self.working_memory.maxlen:
            self._consolidate()
            
    def _add_to_graph(self, item: MemoryItem):
        """Add to hierarchical memory graph"""
        # Find or create node at appropriate level
        level = self._determine_level(item)
        node = MemoryNode(item.content, item.importance, level)
        
        # Find parent (similar content at higher level)
        parent = self._find_parent(node)
        if parent:
            parent.add_child(node)
        else:
            self.memory_graph[id(node)] = node
            
    def _determine_level(self, item: MemoryItem) -> int:
        """Determine abstraction level (0 = concrete, higher = abstract)"""
        # Use embedding similarity to find closest existing nodes
        return min(3, max(0, int(item.importance * 3)))
        
    def _find_parent(self, node: MemoryNode) -> Optional[MemoryNode]:
        """Find most similar node at higher level"""
        best_parent = None
        best_score = 0
        
        for existing_node in self.memory_graph.values():
            if existing_node.level < node.level:
                similarity = self._get_similarity(node.content, existing_node.content)
                if similarity > best_score and similarity > 0.5:
                    best_score = similarity
                    best_parent = existing_node
                    
        return best_parent
        
    def _get_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity"""
        # Use embeddings if available
        # Simple overlap-based fallback
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0
        return len(words1 & words2) / len(words1 | words2)
        
    def _consolidate(self):
        """Consolidate working memory into short-term"""
        # Summarize older items
        if len(self.working_memory) > self.working_memory.maxlen * 0.7:
            old_items = list(self.working_memory)[:-self.working_memory.maxlen//2]
            summary = self._summarize_memory(old_items)
            if summary:
                self.short_term.append(MemoryItem(
                    content=summary,
                    importance=0.5,
                    timestamp=datetime.now(),
                    metadata={"type": "consolidated"}
                ))
                
    def _summarize_memory(self, items: List[MemoryItem]) -> str:
        """Summarize a list of memory items"""
        if not items:
            return ""
        text = "\n".join([item.content for item in items])
        # This would use LLM to summarize in production
        return f"Summary: {text[:200]}..."
        
    def recall(self, query: str, k: int = 5) -> List[MemoryItem]:
        """Retrieve most relevant memories"""
        # Search all memory layers
        results = []
        
        # 1. Working memory (most recent)
        for item in reversed(self.working_memory):
            if query.lower() in item.content.lower():
                results.append(item)
                
        # 2. Short-term memory
        for item in reversed(self.short_term):
            if query.lower() in item.content.lower():
                results.append(item)
                
        # 3. Long-term memory (semantic search would be better)
        for item in self.long_term:
            if query.lower() in item.content.lower():
                results.append(item)
                
        return results[:k]
        
    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """Get relevant context for current query"""
        items = self.recall(query, k=10)
        context = "\n".join([item.content for item in items])
        
        # Trim to max_tokens
        if len(context) > max_tokens:
            context = context[:max_tokens] + "..."
            
        return context
