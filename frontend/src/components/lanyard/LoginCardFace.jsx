import { useState } from 'react'
import './LoginCardFace.css'
import badgeArt from './login-badge-art.png'
import tapeImg from './assets/tape-proto.png'
import hintImg from './assets/hint-text.png'

/**
 * Login UI on the 3D badge face — 1:1 from design assets.
 * Emits to Vue; does not own auth APIs.
 */
export default function LoginCardFace({
  feishuEnabled = false,
  loading = false,
  feishuLoading = false,
  hint = '',
  onSubmit,
  onFeishuLogin,
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('请输入用户名和密码')
      return
    }
    onSubmit?.(username.trim(), password)
  }

  return (
    <div className="login-badge">
      <div className="login-badge__face-layer">
        <img className="login-badge__art" src={badgeArt} alt="" draggable={false} />
        <div className="login-badge__sheen" aria-hidden="true" />
        <div className="login-badge__grain" aria-hidden="true" />
        {/* Knock out the painted black slot so the 3D hook can sit over the card */}
        <div className="login-badge__slot-knockout" aria-hidden="true" />
      </div>
      {/* <img
        className="login-badge__tape"
        src={tapeImg}
        alt=""
        draggable={false}
        aria-hidden="true"
      /> */}

      <div className="login-badge__body">
        <button
          type="button"
          className="login-badge__feishu"
          disabled={!feishuEnabled || feishuLoading}
          onClick={() => {
            if (feishuEnabled) onFeishuLogin?.()
          }}
        >
          {feishuLoading ? '跳转中…' : '飞书登录'}
        </button>

        <form className="login-badge__form" onSubmit={handleSubmit}>
          <input
            className="login-badge__input"
            name="username"
            autoComplete="username"
            placeholder="用户名"
            value={username}
            aria-label="用户名"
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="login-badge__input"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="密  码"
            value={password}
            aria-label="密码"
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="login-badge__error">{error}</p>}
          <button type="submit" className="login-badge__submit" disabled={loading}>
            {loading ? '登录中…' : '登 录'}
          </button>
        </form>

        {feishuEnabled ? (
          <img className="login-badge__hint-img" src={hintImg} alt="" draggable={false} />
        ) : hint ? (
          <p className="login-badge__hint" role="note">
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  )
}
