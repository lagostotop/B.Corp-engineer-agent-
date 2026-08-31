-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector; -- for embeddings
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- ============================================
-- 1. CHATS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);

-- ============================================
-- 2. MESSAGES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    file_meta JSONB,
    client_msg_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_client_msg_id ON messages(client_msg_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- ============================================
-- 3. DOCUMENTS TABLE (RAG)
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- Match OpenAI ada-002
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create HNSW index for fast vector search
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents 
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_documents_chat_id ON documents(chat_id);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);

-- ============================================
-- 4. MEMORY TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS brain30_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, key) -- added so you can upsert
);

CREATE INDEX IF NOT EXISTS idx_memory_user_id ON brain30_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_key ON brain30_memory(key);

-- ============================================
-- 5. INFERENCE LOGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS inference_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    goal TEXT NOT NULL,
    steps JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inference_logs_user_id ON inference_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_inference_logs_created_at ON inference_logs(created_at DESC);

-- ============================================
-- 6. FILE PROCESSING STATUS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS file_processing_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    file_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_status_chat_id ON file_processing_status(chat_id);
CREATE INDEX IF NOT EXISTS idx_file_status_user_id ON file_processing_status(user_id);

-- ============================================
-- 7. FEATURE FLAGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default feature flags
INSERT INTO feature_flags (name, enabled, description) VALUES
    ('deep_research', true, 'Enable deep research capabilities'),
    ('vision_model', true, 'Enable vision model for images'),
    ('code_execution', false, 'Enable code execution (disabled by default for security)'),
    ('rag_enhanced', true, 'Enable RAG with vector search'),
    ('memory_system', true, 'Enable long-term memory'),
    ('multi_agent', true, 'Enable multi-agent collaboration')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- 8. VECTOR SEARCH FUNCTION
-- ============================================
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 3,
    filter_user UUID DEFAULT NULL,
    filter_chat UUID DEFAULT NULL
) RETURNS TABLE(
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE 
        (filter_user IS NULL OR documents.user_id = filter_user)
        AND (filter_chat IS NULL OR documents.chat_id = filter_chat)
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================
-- 9. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain30_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE inference_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_processing_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own chats" ON chats;
CREATE POLICY "Users can view their own chats" ON chats FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own chats" ON chats;
CREATE POLICY "Users can insert their own chats" ON chats FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update their own chats" ON chats;
CREATE POLICY "Users can update their own chats" ON chats FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete their own chats" ON chats;
CREATE POLICY "Users can delete their own chats" ON chats FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own messages" ON messages;
CREATE POLICY "Users can view their own messages" ON messages FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own messages" ON messages;
CREATE POLICY "Users can insert their own messages" ON messages FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete their own messages" ON messages;
CREATE POLICY "Users can delete their own messages" ON messages FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own documents" ON documents;
CREATE POLICY "Users can view their own documents" ON documents FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own documents" ON documents;
CREATE POLICY "Users can insert their own documents" ON documents FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete their own documents" ON documents;
CREATE POLICY "Users can delete their own documents" ON documents FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own memory" ON brain30_memory;
CREATE POLICY "Users can view their own memory" ON brain30_memory FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own memory" ON brain30_memory;
CREATE POLICY "Users can insert their own memory" ON brain30_memory FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update their own memory" ON brain30_memory;
CREATE POLICY "Users can update their own memory" ON brain30_memory FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete their own memory" ON brain30_memory;
CREATE POLICY "Users can delete their own memory" ON brain30_memory FOR DELETE USING (auth.uid() = user_id);

-- ============================================
-- 10. TRIGGERS FOR UPDATED_AT
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_chats_updated_at ON chats;
CREATE TRIGGER update_chats_updated_at 
    BEFORE UPDATE ON chats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_memory_updated_at ON brain30_memory;
CREATE TRIGGER update_memory_updated_at 
    BEFORE UPDATE ON brain30_memory 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_file_status_updated_at ON file_processing_status;
CREATE TRIGGER update_file_status_updated_at 
    BEFORE UPDATE ON file_processing_status 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 11. VIEWS FOR ANALYTICS
-- ============================================
CREATE OR REPLACE VIEW chat_activity AS
SELECT 
    user_id,
    COUNT(DISTINCT id) AS total_chats,
    COUNT(DISTINCT id) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS weekly_chats,
    COUNT(DISTINCT id) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS monthly_chats,
    MAX(updated_at) AS last_active
FROM chats
GROUP BY user_id;

CREATE OR REPLACE VIEW message_stats AS
SELECT 
    chat_id,
    user_id,
    COUNT(*) AS total_messages,
    COUNT(*) FILTER (WHERE role = 'user') AS user_messages,
    COUNT(*) FILTER (WHERE role = 'assistant') AS assistant_messages,
    AVG(LENGTH(content)) AS avg_message_length
FROM messages
GROUP BY chat_id, user_id;
