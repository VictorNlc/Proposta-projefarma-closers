#!/usr/bin/env python3
"""Script para testar se a instalação está correta."""

import sys
import os

def test_imports():
    """Testa se todas as dependências estão instaladas."""
    print("🧪 Testando importações...")
    
    try:
        import flask
        print("  ✅ Flask")
    except ImportError:
        print("  ❌ Flask não instalado")
        return False
    
    try:
        import fitz
        print("  ✅ PyMuPDF")
    except ImportError:
        print("  ❌ PyMuPDF não instalado")
        return False
    
    try:
        from PIL import Image
        print("  ✅ Pillow")
    except ImportError:
        print("  ❌ Pillow não instalado")
        return False
    
    try:
        from openai import OpenAI
        print("  ✅ OpenAI")
    except ImportError:
        print("  ❌ OpenAI não instalado")
        return False
    
    try:
        import openpyxl
        print("  ✅ openpyxl")
    except ImportError:
        print("  ❌ openpyxl não instalado")
        return False
    
    return True

def test_env():
    """Testa se .env está configurado."""
    print("\n🔐 Testando configuração...")
    
    if not os.path.exists('.env'):
        print("  ❌ Arquivo .env não encontrado")
        print("     Execute: cp .env.example .env")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  ❌ OPENAI_API_KEY não configurada em .env")
        return False
    
    if api_key == "sua_chave_aqui":
        print("  ❌ OPENAI_API_KEY ainda é o valor padrão")
        return False
    
    print("  ✅ OPENAI_API_KEY configurada")
    return True

def test_modules():
    """Testa se os módulos principais carregam."""
    print("\n📦 Testando módulos...")
    
    try:
        from catalog import find_catalog_item, get_all_official_names
        print("  ✅ catalog.py")
    except Exception as e:
        print(f"  ❌ catalog.py: {e}")
        return False
    
    try:
        from precision_analyzer import PrecisionAnalyzer
        print("  ✅ precision_analyzer.py")
    except Exception as e:
        print(f"  ❌ precision_analyzer.py: {e}")
        return False
    
    return True

def main():
    print("=" * 50)
    print("🚀 TESTE DE INSTALAÇÃO")
    print("=" * 50)
    
    all_ok = True
    
    if not test_imports():
        all_ok = False
    
    if not test_env():
        all_ok = False
    
    if not test_modules():
        all_ok = False
    
    print("\n" + "=" * 50)
    if all_ok:
        print("✅ TUDO OK! Você pode iniciar com: python app.py")
    else:
        print("❌ Existem problemas. Verifique acima.")
        sys.exit(1)
    print("=" * 50)

if __name__ == "__main__":
    main()
