import json
import os
from datetime import datetime
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string

class ContextManager:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.context_dir = os.path.join(knowledge_dir, "context")
        self.ensure_nltk_data()
        
    def ensure_nltk_data(self):
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('punkt')
            nltk.download('stopwords')
    
    def create_context(self, domain, content):
        context_file = os.path.join(self.context_dir, f"{domain}.json")
        
        context = {
            "domain": domain,
            "content": content,
            "keywords": self.extract_keywords(content),
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        if os.path.exists(context_file):
            with open(context_file, 'r') as f:
                existing = json.load(f)
                context["created"] = existing.get("created", context["created"])
        
        with open(context_file, 'w') as f:
            json.dump(context, f, indent=2)
    
    def get_context(self, domain):
        context_file = os.path.join(self.context_dir, f"{domain}.json")
        if os.path.exists(context_file):
            with open(context_file, 'r') as f:
                return json.load(f)
        return None
    
    def update_context(self, domain, new_content):
        existing = self.get_context(domain)
        if existing:
            existing["content"] += "\n" + new_content
            existing["keywords"] = self.extract_keywords(existing["content"])
            existing["last_updated"] = datetime.now().isoformat()
            
            context_file = os.path.join(self.context_dir, f"{domain}.json")
            with open(context_file, 'w') as f:
                json.dump(existing, f, indent=2)
    
    def extract_keywords(self, text):
        # Tokenize and clean text
        tokens = word_tokenize(text.lower())
        stop_words = set(stopwords.words('english'))
        tokens = [w for w in tokens if w not in stop_words and w not in string.punctuation]
        
        # Count word frequencies
        freq = nltk.FreqDist(tokens)
        
        # Return most common keywords
        return [word for word, count in freq.most_common(10)]
    
    def find_relevant_contexts(self, query):
        relevant = []
        query_keywords = set(self.extract_keywords(query))
        
        for file in os.listdir(self.context_dir):
            if file.endswith('.json'):
                context = self.get_context(file[:-5])  # Remove .json
                if context:
                    context_keywords = set(context['keywords'])
                    overlap = len(query_keywords & context_keywords)
                    if overlap > 0:
                        relevant.append({
                            "domain": context['domain'],
                            "relevance": overlap / len(query_keywords),
                            "content": context['content']
                        })
        
        return sorted(relevant, key=lambda x: x['relevance'], reverse=True) 