/**
 * Vlog 自动剪辑工具 - 主应用组件
 *
 * 提供视频上传、文案输入、一键剪辑和下载功能。
 * 文案按段落分割，每个段落对应视频中的一个剪辑片段。
 */

import { useState, useCallback } from 'react'
import './App.css'

const API_BASE = '/api'

export default function App() {
  const [script, setScript] = useState('')
  const [files, setFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      /\.(mp4|mov|avi|mkv|webm)$/i.test(f.name)
    )
    if (dropped.length) {
      setFiles((prev) => [...prev, ...dropped])
    }
  }, [])

  const handleFileInput = (e) => {
    const selected = Array.from(e.target.files || []).filter((f) =>
      /\.(mp4|mov|avi|mkv|webm)$/i.test(f.name)
    )
    if (selected.length) {
      setFiles((prev) => [...prev, ...selected])
    }
    e.target.value = ''
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    setError('')
    setResult(null)
    if (!script.trim()) {
      setError('请输入文案')
      return
    }
    if (files.length === 0) {
      setError('请至少上传一个视频文件')
      return
    }

    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('script', script.trim())
      files.forEach((f) => formData.append('files', f))

      const res = await fetch(`${API_BASE}/process`, {
        method: 'POST',
        body: formData,
      })

      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || res.statusText || '处理失败')
      }
      setResult(data)
    } catch (err) {
      setError(err.message || '剪辑失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const downloadUrl = result?.download_url || ''

  return (
    <div className="app">
      <header className="header">
        <h1>Vlog 自动剪辑</h1>
        <p>上传视频素材和文案，一键生成与文案段落对应的 vlog 视频</p>
      </header>

      <main className="main">
        <section className="card">
          <h2>文案</h2>
          <p className="hint">按段落输入文案，每个空行分隔的段落将对应视频中的一个剪辑片段</p>
          <textarea
            className="script-input"
            placeholder="例如：&#10;&#10;今天天气真好，出门散散步。&#10;&#10;路过一家咖啡店，进去坐坐。&#10;&#10;咖啡很香，心情也不错。"
            value={script}
            onChange={(e) => setScript(e.target.value)}
            rows={8}
          />
        </section>

        <section className="card">
          <h2>视频素材</h2>
          <p className="hint">支持 MP4、MOV、AVI、MKV、WebM，可上传多个视频</p>
          <div
            className={`dropzone ${dragActive ? 'active' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept=".mp4,.mov,.avi,.mkv,.webm"
              multiple
              onChange={handleFileInput}
              id="file-input"
            />
            <label htmlFor="file-input" className="dropzone-label">
              点击或拖拽视频到此处上传
            </label>
          </div>
          {files.length > 0 && (
            <ul className="file-list">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`}>
                  <span>{f.name}</span>
                  <button type="button" onClick={() => removeFile(i)} aria-label="移除">
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        <button
          className="submit-btn"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? '剪辑中…' : '开始剪辑'}
        </button>

        {result && (
          <section className="card result-card">
            <h2>剪辑完成</h2>
            <p>视频已根据文案段落自动切割并拼接完成。</p>
            <a
              href={downloadUrl}
              download={`vlog_${result.task_id?.slice(0, 8) || 'output'}.mp4`}
              className="download-btn"
            >
              下载视频
            </a>
          </section>
        )}
      </main>

      <footer className="footer">
        <p>使用 FFmpeg 进行视频处理，请确保本地已安装 FFmpeg</p>
      </footer>
    </div>
  )
}
