# Vlog 自动剪辑工具

根据上传的视频素材和文案，自动将视频切割成与文案段落对应的片段并拼接成完整 vlog。

**GitHub**: https://github.com/kaobaobao888/vlog-cut

## 功能

- 上传多个视频素材（支持 MP4、MOV、AVI、MKV、WebM）
- 输入文案，按段落（空行分隔）自动分段
- 每个文案段落对应一个视频剪辑片段
- 自动按比例分配视频时长并拼接输出

## 技术栈

- **前端**: React + Vite
- **后端**: Python FastAPI
- **视频处理**: FFmpeg

## 环境要求

- Node.js 18+
- Python 3.10+
- FFmpeg（需已安装并加入 PATH）

## 本地运行

### 1. 安装 FFmpeg

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

后端将运行在 http://localhost:8000

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端将运行在 http://localhost:5173，并代理 API 请求到后端。

### 4. 使用

1. 在文案框输入内容，用空行分隔不同段落
2. 上传一个或多个视频
3. 点击「开始剪辑」
4. 等待处理完成后下载视频

## 在线部署

### Render（推荐）

1. 登录 [Render](https://render.com)
2. 点击 New → Web Service
3. 连接 GitHub 仓库 `kaobaobao888/vlog-cut`
4. 选择 Docker 部署，使用项目根目录的 Dockerfile
5. 创建服务后即可获得在线访问地址

### Docker 本地运行

```bash
docker build -t vlog-cut .
docker run -p 8000:8000 vlog-cut
```

访问 http://localhost:8000

## 项目结构

```
vlog cut/
├── backend/          # FastAPI 后端
│   ├── main.py       # 主程序
│   └── requirements.txt
├── frontend/         # React 前端
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## License

MIT
