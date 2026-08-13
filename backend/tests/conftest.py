import os


os.environ["STORAGE_BACKEND"] = "memory"
os.environ["AUTO_CREATE_SCHEMA"] = "false"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MASTER_ENCRYPTION_KEY"] = "test-only-master-encryption-key"
