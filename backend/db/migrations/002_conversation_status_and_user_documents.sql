-- =========================================================
-- 002_conversation_status_and_user_documents.sql
-- Adds status tracking and archive capabilities to conversations and messages.
-- Safe and idempotent: can be run repeatedly without breaking existing data.
-- =========================================================

-- Add status column to conversations if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'conversations' 
          AND column_name = 'status'
    ) THEN
        ALTER TABLE public.conversations 
        ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived'));
    END IF;
END $$;

-- Add status column to messages if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'messages' 
          AND column_name = 'status'
    ) THEN
        ALTER TABLE public.messages 
        ADD COLUMN status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed'));
    END IF;
END $$;

-- Add performance indexes for status-based filtering
CREATE INDEX IF NOT EXISTS idx_conversations_user_status ON public.conversations(user_id, status, last_message_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_messages_conv_status ON public.messages(conversation_id, status);
