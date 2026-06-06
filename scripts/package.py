import os
import shutil
import zipfile
import datetime
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CODE_DIR = BASE_DIR / "code" / "unified_auth"
DIST_DIR = BASE_DIR / "dist"
LOG_DIR = BASE_DIR / "scripts" / "package"

INCLUDE_PATTERNS = [
    "*.py",
    "*.json",
    "*.yml",
    "*.yaml",
    "*.md",
    "*.sh",
    "*.sql",
    "*.ini",
    "*.env.example",
    "*.html",
    "*.css",
    "*.js",
    "*.svg",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.ico",
    "*.map",
    "LICENSE*",
    "README*",
]

EXCLUDE_DIRS = [
    "__pycache__",
    ".git",
    ".trae",
    "node_modules",
    "tests",
    ".pytest_cache",
    ".tox",
    "venv",
    "env",
]

EXCLUDE_FILES = [
    ".gitignore",
    ".env",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
]


def setup_logging(log_file_path):
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def should_include_file(file_path):
    file_name = file_path.name
    for pattern in EXCLUDE_FILES:
        if file_name.endswith(pattern.replace("*", "")) or file_name == pattern.replace("*", ""):
            return False
    return True


def should_include_dir(dir_path):
    dir_name = dir_path.name
    for exclude in EXCLUDE_DIRS:
        if dir_name == exclude:
            return False
    return True


def collect_files(source_dir):
    files_to_package = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if should_include_dir(Path(root) / d)]
        for file in files:
            file_path = Path(root) / file
            if should_include_file(file_path):
                files_to_package.append(file_path)
    return files_to_package


def copy_to_dist(source_dir, dist_dir):
    files_copied = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if should_include_dir(Path(root) / d)]
        for file in files:
            source_file = Path(root) / file
            if not should_include_file(source_file):
                continue
            rel_path = source_file.relative_to(source_dir)
            dest_file = dist_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)
            files_copied.append(rel_path)
            logging.info(f"Copied: {rel_path}")
    return files_copied


def create_zip(dist_dir, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(dist_dir.parent)
                zf.write(file_path, arcname)
                logging.info(f"Added to zip: {arcname}")


def check_migrations(source_dir):
    migrations = []
    apps_dir = source_dir / "apps"
    if not apps_dir.exists():
        return migrations
    
    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue
        migrations_dir = app_dir / "migrations"
        if not migrations_dir.exists():
            continue
        
        for file in migrations_dir.iterdir():
            if file.is_file() and file.name.startswith("00") and file.name.endswith(".py"):
                migrations.append({
                    "app": app_dir.name,
                    "migration": file.name
                })
    
    return migrations


def generate_update_notes(dist_dir, migrations, today):
    notes = []
    notes.append("=" * 60)
    notes.append(f"更新说明 - {today}")
    notes.append("=" * 60)
    notes.append("")
    
    if migrations:
        notes.append("【数据库更新】")
        notes.append("检测到以下迁移文件，请根据需要执行数据库更新：")
        notes.append("")
        for migration in sorted(migrations, key=lambda x: (x["app"], x["migration"])):
            notes.append(f"  - {migration['app']}: {migration['migration']}")
        notes.append("")
        notes.append("执行数据库更新的命令：")
        notes.append("  cd dist")
        notes.append("  python manage.py migrate")
        notes.append("")
    else:
        notes.append("【数据库更新】")
        notes.append("未检测到新的数据库迁移文件")
        notes.append("")
    
    notes.append("【部署步骤】")
    notes.append("1. 备份现有数据库和配置文件")
    notes.append("2. 停止服务")
    notes.append("3. 替换文件")
    if migrations:
        notes.append("4. 执行数据库迁移: python manage.py migrate")
    notes.append("5. 启动服务")
    notes.append("")
    notes.append("=" * 60)
    
    notes_content = "\n".join(notes)
    
    notes_file = dist_dir / "UPDATE_NOTES.txt"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(notes_content)
    
    for line in notes:
        logging.info(line)
    
    return notes_file


def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    log_file_path = LOG_DIR / f"{today}.log"
    setup_logging(log_file_path)
    
    logging.info("=" * 60)
    logging.info(f"Packaging started at {datetime.datetime.now()}")
    logging.info("=" * 60)
    
    try:
        if DIST_DIR.exists():
            shutil.rmtree(DIST_DIR)
            logging.info(f"Removed existing dist directory: {DIST_DIR}")
        
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        logging.info(f"Created dist directory: {DIST_DIR}")
        
        copied_files = copy_to_dist(CODE_DIR, DIST_DIR)
        logging.info(f"Total files copied: {len(copied_files)}")
        
        migrations = check_migrations(CODE_DIR)
        if migrations:
            logging.info(f"Detected {len(migrations)} migration files")
        
        generate_update_notes(DIST_DIR, migrations, today)
        
        zip_path = BASE_DIR / f"unified_auth_{today}.zip"
        if zip_path.exists():
            zip_path.unlink()
            logging.info(f"Removed existing zip: {zip_path}")
        
        create_zip(DIST_DIR, zip_path)
        logging.info(f"Created zip archive: {zip_path}")
        
        logging.info("=" * 60)
        logging.info("Packaging completed successfully!")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error(f"Packaging failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()