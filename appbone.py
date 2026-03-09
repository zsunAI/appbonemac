# -*- coding: utf-8 -*-
"""
Created on Fri Jan 30 18:32:03 2026

@author: admin
"""
import os
import sys
import glob
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_file
import chardet
import random
def get_resource_path(relative_path):
    """获取资源文件路径，兼容打包环境"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()

app = Flask(__name__,
            template_folder=os.path.join(BASE_PATH, 'templates'),
            static_folder=os.path.join(BASE_PATH, 'static'))

DATA_FOLDER = Path.cwd() / 'data'
IMAGE_FOLDER = Path.cwd() / 'data'
RESULTS_FOLDER = Path.cwd() / 'scoring_resultsAI'
SCORES_FILE = Path.cwd() / 'scores.json'
VAL_CSV_FILE = Path.cwd() / 'val_info2.csv'

os.makedirs(RESULTS_FOLDER, exist_ok=True)

DISEASE_NAMES = [
    '脑实质内出血', '脑室内出血', '硬膜下出血', '硬膜外出血', '蛛网膜下出血',
    '急性缺血性脑卒中', '肿瘤', '骨折', '脑疝', '脑积水', '血管畸形'
]

DISEASE_PROB_COLS = [d + '_prob' for d in DISEASE_NAMES]

def prob_to_level(prob: float) -> int:
    """将概率值转换为1-5的评分等级"""
    if prob < 0.1:
        return 1
    elif prob < 0.4:
        return 2
    elif prob < 0.6:
        return 3
    elif prob < 0.8:
        return 4
    else:
        return 5

def load_ai_scores() -> dict:
    """从CSV文件加载AI评分数据"""
    ai_data = {}
    if not os.path.exists(VAL_CSV_FILE):
        print(f"[警告] AI CSV 文件不存在: {VAL_CSV_FILE}")
        return ai_data
    
    try:
        with open(VAL_CSV_FILE, 'rb') as f:
            encoding = chardet.detect(f.read())['encoding']
        
        with open(VAL_CSV_FILE, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                sub_id = row.get('Sub_ID', '').strip()
                if not sub_id:
                    continue
                
                disease_scores = {}
                for disease, col in zip(DISEASE_NAMES, DISEASE_PROB_COLS):
                    raw = row.get(col, '').strip()
                    try:
                        prob = float(raw)
                    except (ValueError, TypeError):
                        prob = 0.0
                    
                    disease_scores[disease] = {
                        'prob': round(prob, 4),
                        'level': prob_to_level(prob)
                    }
                
                ai_data[sub_id] = disease_scores
        
        print(f"[信息] 已读取 AI CSV，共 {len(ai_data)} 条记录")
    except Exception as e:
        print(f"[错误] 读取 AI CSV 失败: {e}")
        import traceback
        traceback.print_exc()
    
    return ai_data

AI_SCORES: dict = load_ai_scores()

current_session: dict = {}

def get_patient_folders_old():
    """获取所有患者的基础ID（不含bone后缀）"""
    folders = []
    seen_base_ids = set()
    
    if not os.path.exists(IMAGE_FOLDER):
        print(f"[警告] 图像文件夹不存在: {IMAGE_FOLDER}")
        return folders
    for item in os.listdir(IMAGE_FOLDER):
        item_path = os.path.join(IMAGE_FOLDER, item)
        if os.path.isdir(item_path):
            png_files = glob.glob(os.path.join(item_path, '*.png'))
            if png_files:
                base_id = item.replace('bone', '') if item.endswith('bone') else item
                if base_id not in seen_base_ids:
                    seen_base_ids.add(base_id)
                    folders.append(base_id)
    
    return sorted(folders)
def get_patient_folders():
    """获取所有患者的基础ID（不含bone后缀）"""
    folders = []
    seen_base_ids = set()
    
    if not os.path.exists(IMAGE_FOLDER):
        print(f"[警告] 图像文件夹不存在: {IMAGE_FOLDER}")
        return folders
    
    for item in os.listdir(IMAGE_FOLDER):
        item_path = os.path.join(IMAGE_FOLDER, item)
        if os.path.isdir(item_path):
            png_files = glob.glob(os.path.join(item_path, '*.png'))
            if png_files:
                # 提取基础ID（去除bone后缀）
                base_id = item.replace('bone', '') if item.endswith('bone') else item
                if base_id not in seen_base_ids:
                    seen_base_ids.add(base_id)
                    folders.append(base_id)
    
    # 随机打乱顺序
    folders.sort()
    random.seed(42)
    random.shuffle(folders)
    return folders
def get_window_folders(base_id):
    """获取患者的软组织窗和骨窗文件夹"""
    soft_folder = base_id
    bone_folder = base_id + 'bone'
    
    result = {}
    
    # 检查软组织窗
    soft_path = os.path.join(IMAGE_FOLDER, soft_folder)
    if os.path.exists(soft_path) and os.path.isdir(soft_path):
        png_files = glob.glob(os.path.join(soft_path, '*.png'))
        if png_files:
            result['soft'] = {
                'folder': soft_folder,
                'count': len(png_files)
            }
    
    # 检查骨窗
    bone_path = os.path.join(IMAGE_FOLDER, bone_folder)
    if os.path.exists(bone_path) and os.path.isdir(bone_path):
        png_files = glob.glob(os.path.join(bone_path, '*.png'))
        if png_files:
            result['bone'] = {
                'folder': bone_folder,
                'count': len(png_files)
            }
    
    return result
def get_png_files(folder_name):
    """获取指定文件夹中的所有PNG文件"""
    folder_path = os.path.join(IMAGE_FOLDER, folder_name)
    png_files = sorted(glob.glob(os.path.join(folder_path, '*.png')))
    print(f"找到 {len(png_files)} 个PNG文件在 {folder_name}")
    return png_files

def check_if_scored(folder_name):
    """检查患者是否已经完成评分"""
    result_file = os.path.join(RESULTS_FOLDER, f"{folder_name}_result.txt")
    return os.path.exists(result_file)

def get_ai_levels_for_folder(folder_name: str) -> dict:
    """获取指定文件夹的AI预设评分等级"""
    if folder_name in AI_SCORES:
        return AI_SCORES[folder_name]
    return {d: {'prob': None, 'level': None} for d in DISEASE_NAMES}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/folders')
def get_folders():
    """获取所有患者列表及评分状态"""
    try:
        base_ids = get_patient_folders()
        folder_list = []
        scored_count = 0

        for base_id in base_ids:
            windows = get_window_folders(base_id)
            is_scored = check_if_scored(base_id)
            if is_scored:
                scored_count += 1
            
            folder_list.append({
                'name': base_id,
                'has_soft': 'soft' in windows,
                'has_bone': 'bone' in windows,
                'soft_count': windows.get('soft', {}).get('count', 0),
                'bone_count': windows.get('bone', {}).get('count', 0),
                'scored': is_scored
            })

        return jsonify({
            'folders': folder_list,
            'total': len(base_ids),
            'scored': scored_count
        })

    except Exception as e:
        print(f"获取文件夹列表错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'folders': [], 'total': 0, 'scored': 0, 'error': str(e)})

@app.route('/api/load_folder/<base_id>')
def load_folder(base_id):
    """加载患者的软组织窗和骨窗图像"""
    windows = get_window_folders(base_id)
    
    if not windows:
        return jsonify({'success': False, 'error': '未找到图像文件夹'})
    
    result = {
        'success': True,
        'base_id': base_id,
        'windows': {}
    }
    
    # 加载软组织窗
    if 'soft' in windows:
        soft_folder = windows['soft']['folder']
        soft_files = sorted(glob.glob(os.path.join(IMAGE_FOLDER, soft_folder, '*.png')))
        result['windows']['soft'] = {
            'folder': soft_folder,
            'num_images': len(soft_files),
            'images': [f"/api/get_image/{soft_folder}/{os.path.basename(p)}" for p in soft_files]
        }
    
    # 加载骨窗
    if 'bone' in windows:
        bone_folder = windows['bone']['folder']
        bone_files = sorted(glob.glob(os.path.join(IMAGE_FOLDER, bone_folder, '*.png')))
        result['windows']['bone'] = {
            'folder': bone_folder,
            'num_images': len(bone_files),
            'images': [f"/api/get_image/{bone_folder}/{os.path.basename(p)}" for p in bone_files]
        }
    
    # 获取AI评分（使用基础ID）
    ai_levels = get_ai_levels_for_folder(base_id)
    matched = base_id in AI_SCORES
    
    result['ai_matched'] = matched
    result['ai_levels'] = ai_levels
    
    # 记录会话开始时间
    current_session[base_id] = {
        'start_time': datetime.now(),
        'base_id': base_id
    }
    print(f"开始计时: {base_id} at {current_session[base_id]['start_time']}")
    
    return jsonify(result)




@app.route('/api/get_image/<folder_name>/<filename>')
def get_image(folder_name, filename):
    """获取指定图像文件"""
    try:
        image_path = os.path.join(IMAGE_FOLDER, folder_name, filename)
        return send_file(image_path, mimetype='image/png')
    except Exception as e:
        print(f"获取图像错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit_score', methods=['POST'])
def submit_score():
    """提交医生最终评分，保存结果文件"""
    try:
        data = request.json
        base_id = data.get('folder_name', '')  # 使用基础ID
        final_scores = data.get('final_scores', {})
        ai_scores_fe = data.get('ai_scores', {})

        elapsed_time = 0.0
        end_time = datetime.now()
        if base_id in current_session and current_session[base_id].get('start_time'):
            elapsed_time = (end_time - current_session[base_id]['start_time']).total_seconds()
        open_time = end_time - timedelta(seconds=elapsed_time)

        if not ai_scores_fe:
            ai_levels = get_ai_levels_for_folder(base_id)
            ai_scores_fe = {d: info['level'] for d, info in ai_levels.items()}

        # 使用基础ID保存结果
        result_file = os.path.join(RESULTS_FOLDER, f"{base_id}_result.txt")
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"患者ID: {base_id}\n")
            f.write(f"打开时间: {open_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"提交时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"用时: {elapsed_time:.2f} 秒\n")
            f.write("\n--- 疾病评分详情 ---\n")
            for disease in DISEASE_NAMES:
                ai_lvl = ai_scores_fe.get(disease, 'N/A')
                final_lvl = final_scores.get(disease, 'N/A')
                modified = '(医生已修改)' if str(ai_lvl) != str(final_lvl) else ''
                f.write(f"  {disease}: AI预设={ai_lvl}  医生最终={final_lvl}  {modified}\n")

        if base_id in current_session:
            del current_session[base_id]

        print(f"评分已保存: {base_id} | 用时: {elapsed_time:.2f}s")

        return jsonify({'success': True, 'elapsed_time': elapsed_time})

    except Exception as e:
        print(f"提交评分错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/results')
def get_results():
    """获取所有已完成的评分结果摘要"""
    try:
        results = []
        for filename in os.listdir(RESULTS_FOLDER):
            if not filename.endswith('_result.txt'):
                continue
            filepath = os.path.join(RESULTS_FOLDER, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            result_data = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    result_data[key.strip()] = value.strip()
            
            results.append({
                'folder_name': result_data.get('患者文件夹', ''),
                'time': result_data.get('用时', ''),
                'submit_time': result_data.get('提交时间', '')
            })

        results.sort(key=lambda x: x.get('submit_time', ''), reverse=True)
        return jsonify({'results': results})

    except Exception as e:
        print(f"获取结果错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'results': [], 'error': str(e)})

if __name__ == '__main__':
    print("=" * 50)
    print("启动 Flask 服务器...")
    print(f"图像文件夹: {IMAGE_FOLDER}")
    print(f"结果文件夹: {RESULTS_FOLDER}")
    print(f"AI CSV 文件: {VAL_CSV_FILE}")
    print(f"AI 记录数量: {len(AI_SCORES)}")
    print(f"访问地址:   http://localhost:5001")
    print("=" * 50)

    folders = get_patient_folders()
    print(f"找到 {len(folders)} 个患者文件夹")
    if folders:
        print(f"示例文件夹: {folders[:3]}")

    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
