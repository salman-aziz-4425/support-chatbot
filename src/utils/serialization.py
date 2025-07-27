import logging

logger = logging.getLogger(__name__)

def safe_serialize_content(content):
    """Safely serialize content that might contain FunctionCall objects"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        serialized_items = []
        for item in content:
            try:
                if hasattr(item, 'name') and hasattr(item, 'arguments'):
                    serialized_items.append(f"Function call: {item.name}")
                else:
                    item_str = str(item)
                    import json
                    json.dumps(item_str)
                    serialized_items.append(item_str)
            except Exception:
                serialized_items.append(f"[Unserializable item: {type(item).__name__}]")
        
        return "; ".join(serialized_items) if serialized_items else "Processing request..."
    else:
        return str(content) 