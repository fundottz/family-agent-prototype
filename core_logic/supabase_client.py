"""Supabase client configuration and utilities."""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_supabase_client() -> Client:
    """Создает и возвращает клиент Supabase."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env file. "
            "Get them from your Supabase project settings."
        )
    
    return create_client(url, key)


def get_supabase_service_client() -> Client:
    """Создает клиент с service_role ключом (для админских операций)."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file."
        )
    
    return create_client(url, key)

