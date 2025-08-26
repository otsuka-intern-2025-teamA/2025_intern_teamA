"""
FastAPI バックエンドとの通信ライブラリ
案件データの取得・操作をAPI経由で実行
"""
import requests
import json
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class APIClient:
    """FastAPI バックエンドへのHTTPクライアント"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        HTTP リクエストを実行し、結果をJSONで返す
        エラーハンドリング付き
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        except requests.exceptions.ConnectionError:
            logger.error(f"API接続エラー: {url}")
            raise APIConnectionError("バックエンドサーバーに接続できません")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP エラー {e.response.status_code}: {url}")
            if e.response.status_code == 404:
                raise APINotFoundError("リソースが見つかりません")
            elif e.response.status_code >= 500:
                raise APIServerError("サーバーエラーが発生しました")
            else:
                raise APIError(f"API エラー: {e.response.status_code}")
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            raise APIError(f"予期しないエラーが発生しました: {e}")
    
    # === 案件管理 API ===
    
    def get_items(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """案件一覧を取得（サマリ情報付き）"""
        return self._make_request("GET", f"/items?skip={skip}&limit={limit}")
    
    def get_item(self, item_id: str) -> Dict[str, Any]:
        """指定案件の詳細を取得"""
        return self._make_request("GET", f"/items/{item_id}")
    
    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """新規案件を作成"""
        return self._make_request("POST", "/items", json=data)
    
    def update_item(self, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """案件情報を更新"""
        return self._make_request("PUT", f"/items/{item_id}", json=data)
    
    def delete_item(self, item_id: str):
        """案件を削除"""
        response = self._make_request("DELETE", f"/items/{item_id}")
        return
    
    # === メッセージ管理 API ===
    
    def get_messages(
        self, 
        item_id: str, 
        skip: int = 0, 
        limit: int = 50, 
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """案件内のメッセージ一覧を取得"""
        params = f"?skip={skip}&limit={limit}"
        if search:
            params += f"&search={search}"
        return self._make_request("GET", f"/items/{item_id}/messages{params}")
    
    def create_message(self, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """新規メッセージを作成"""
        return self._make_request("POST", f"/items/{item_id}/messages", json=data)
    
    # === 企業分析 API ===
    
    def analyze_company(
        self, 
        item_id: str, 
        question: str, 
        company_name: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """企業分析を実行"""
        data = {
            "item_id": item_id,
            "question": question,
            "top_k": top_k
        }
        if company_name:
            data["company_name"] = company_name
        
        return self._make_request("POST", "/analysis/query", json=data)
    
    def load_history(self, item_id: str, company_name: str) -> Dict[str, Any]:
        """取引履歴をロード"""
        data = {
            "item_id": item_id,
            "company_name": company_name
        }
        return self._make_request("POST", "/analysis/history/load", json=data)
    
    # === ヘルスチェック ===
    
    def health_check(self) -> Dict[str, Any]:
        """APIサーバーのヘルスチェック"""
        return self._make_request("GET", "/health")

# === 例外クラス ===

class APIError(Exception):
    """API関連の基底例外"""
    pass

class APIConnectionError(APIError):
    """API接続エラー"""
    pass

class APINotFoundError(APIError):
    """リソースが見つからないエラー"""
    pass

class APIServerError(APIError):
    """サーバーエラー"""
    pass

# === シングルトンクライアント ===

# グローバルなAPIクライアントインスタンス
_api_client = None

def get_api_client() -> APIClient:
    """APIクライアントのシングルトンインスタンスを取得"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client

# === 便利関数 ===

def api_available() -> bool:
    """APIサーバーが利用可能かチェック"""
    try:
        client = get_api_client()
        client.health_check()
        return True
    except Exception:
        return False

def format_date(date_str: str) -> str:
    """ISO形式の日付文字列を表示用にフォーマット"""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%Y/%m/%d")
    except Exception:
        return date_str