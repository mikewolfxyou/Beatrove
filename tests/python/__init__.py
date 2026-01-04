import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'fastapi\.routing')
warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'starlette\._utils')
warnings.filterwarnings('ignore', category=ResourceWarning, module=r'anyio\._backends\._asyncio')
