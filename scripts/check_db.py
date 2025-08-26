#!/usr/bin/env python3
"""
データベースの内容を確認するスクリプト
"""

import argparse
import sqlite3
from pathlib import Path


def check_database(show_all_data=False, max_sample_size=20):
    db_path = Path("data/sqlite/app.db")

    if not db_path.exists():
        print(f"データベースファイルが見つかりません: {db_path}")
        return

    print(f"データベースファイル: {db_path}")
    print(f"ファイルサイズ: {db_path.stat().st_size} bytes")
    print("=" * 50)

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        print("データベース内のテーブル一覧:")
        for table in tables:
            print(f"- {table[0]}")

        print("\n" + "=" * 50)

        # 各テーブルの内容を確認
        for table in tables:
            table_name = table[0]
            print(f"\n📋 テーブル: {table_name}")
            print("-" * 30)

            # テーブルのスキーマを確認
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print("カラム情報:")
            for col in columns:
                nullable = "NOT NULL" if col[3] else "NULL"
                primary = "PRIMARY KEY" if col[5] else ""
                print(f"  {col[1]} ({col[2]}) - {nullable} - {primary}")

            # レコード数を確認
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"\nレコード数: {count}")

            # データの表示
            if count > 0:
                if show_all_data or count <= max_sample_size:
                    # 全データまたはサンプルサイズ以下の場合は全件表示
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()
                    print(f"全データ（{count}件）:")
                    for i, row in enumerate(rows, 1):
                        print(f"  {i}: {row}")
                else:
                    # サンプルサイズを超える場合は最初のN件と最後のN件を表示
                    limit_query = f"SELECT * FROM {table_name} LIMIT {max_sample_size}"
                    cursor.execute(limit_query)
                    first_rows = cursor.fetchall()

                    desc_query = f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT {max_sample_size}"
                    cursor.execute(desc_query)
                    last_rows = cursor.fetchall()
                    last_rows.reverse()  # 順序を元に戻す

                    print(f"サンプルデータ（最初の{max_sample_size}件）:")
                    for i, row in enumerate(first_rows, 1):
                        print(f"  {i}: {row}")

                    if count > max_sample_size * 2:
                        middle_count = count - max_sample_size * 2
                        print(f"  ... 中略（{middle_count}件）...")

                    print(f"サンプルデータ（最後の{max_sample_size}件）:")
                    for i, row in enumerate(last_rows, 1):
                        row_num = i + count - max_sample_size
                        print(f"  {row_num}: {row}")
            else:
                print("データがありません")

            print()

        # ビューの確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = cursor.fetchall()
        if views:
            print("📊 ビュー一覧:")
            for view in views:
                print(f"- {view[0]}")

                # ビューの内容を確認
                cursor.execute(f"SELECT COUNT(*) FROM {view[0]}")
                view_count = cursor.fetchone()[0]
                print(f"  レコード数: {view_count}")

                if view_count > 0:
                    if show_all_data or view_count <= max_sample_size:
                        cursor.execute(f"SELECT * FROM {view[0]}")
                        view_rows = cursor.fetchall()
                        print(f"  全データ（{view_count}件）:")
                        for i, row in enumerate(view_rows, 1):
                            print(f"    {i}: {row}")
                    else:
                        cursor.execute(f"SELECT * FROM {view[0]} LIMIT {max_sample_size}")
                        view_rows = cursor.fetchall()
                        print(f"  サンプルデータ（最初の{max_sample_size}件）:")
                        for i, row in enumerate(view_rows, 1):
                            print(f"    {i}: {row}")
                        print(f"    ... 他 {view_count - max_sample_size} 件")
                print()

        # インデックスの確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        if indexes:
            print("🔍 インデックス一覧:")
            for index in indexes:
                print(f"- {index[0]}")

        conn.close()

    except Exception as e:
        print(f"エラーが発生しました: {e}")


def main():
    parser = argparse.ArgumentParser(description="データベースの内容を確認するスクリプト")
    parser.add_argument("--all", action="store_true", help="全てのデータを表示（サンプルではなく）")
    parser.add_argument("--max-sample", type=int, default=20, help="サンプル表示の最大件数（デフォルト: 20）")

    args = parser.parse_args()

    check_database(show_all_data=args.all, max_sample_size=args.max_sample)


if __name__ == "__main__":
    main()
