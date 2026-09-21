"""
plugins/software_dev_controller.py — Software Development Controller for JARVIS.

Enables JARVIS to autonomously manage software development workflows:
1. Scaffolds new projects with complete code (HTML/CSS/JS, Python, React, etc.).
2. Specializes in rapid component generation (e.g., modern login pages, dashboards, web apps).
3. Opens the project and files in Google Antigravity IDE.
4. Launches autonomous Antigravity coding agents via the `chat` subcommand.
5. Launches instant live browser previews for web applications.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
PROJECTS_DIR = Path("F:/jarvis/projects") if Path("F:/jarvis").exists() else (BASE_DIR / "projects")

PLUGIN = {
    "name": "software_dev_controller",
    "description": (
        "Controls software development, project creation, and coding in Google Antigravity IDE. "
        "Use this whenever the user asks to build, create, develop, or code any software, website, "
        "web page, or application (e.g., 'build a login page', 'create a login page in antigravity', "
        "'build a web app', 'code a dashboard', 'create a new project', 'start coding in antigravity', "
        "'develop a landing page', 'open antigravity', 'build a portfolio website'). "
        "Automatically creates a project folder, writes complete responsive code, opens Antigravity IDE, "
        "and launches a live browser preview."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "The action to execute: 'create_project' (build, code, and open project in Antigravity), "
                    "'open_ide' (launch Antigravity IDE at project directory), "
                    "'prompt_agent' (send task prompt to Antigravity autonomous agent), "
                    "'preview' (open live browser preview of project)."
                ),
            },
            "project_name": {
                "type": "STRING",
                "description": "Short folder/project name (e.g., 'login-page', 'crypto-dashboard', 'portfolio').",
            },
            "project_type": {
                "type": "STRING",
                "description": "Project category: 'web' (HTML/CSS/JS), 'python', 'react', or 'auto'. Default: 'auto'.",
            },
            "prompt": {
                "type": "STRING",
                "description": "Detailed requirements of what to build or what the Antigravity agent should do.",
            },
            "open_browser": {
                "type": "BOOLEAN",
                "description": "Whether to open live browser preview immediately (default: true).",
            },
        },
        "required": ["action"],
    },
}


def _find_antigravity_ide() -> Optional[str]:
    """Locates the Antigravity IDE executable on Windows."""
    # 1. Check system PATH
    which_path = shutil.which("antigravity-ide") or shutil.which("antigravity-ide.cmd")
    if which_path:
        return which_path

    # 2. Known default Windows installation paths
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    candidates = [
        os.path.join(local_app_data, "Programs", "Antigravity IDE", "bin", "antigravity-ide.cmd"),
        os.path.join(local_app_data, "Programs", "Antigravity IDE", "Antigravity IDE.exe"),
        os.path.join(program_files, "Antigravity IDE", "bin", "antigravity-ide.cmd"),
        os.path.join(program_files, "Antigravity IDE", "Antigravity IDE.exe"),
        "C:\\Users\\mgdha\\AppData\\Local\\Programs\\Antigravity IDE\\bin\\antigravity-ide.cmd",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    return None


def _sanitize_name(name: str) -> str:
    """Sanitize project name for directory creation."""
    s = re.sub(r"[^\w\s-]", "", name).strip().lower()
    s = re.sub(r"[-\s]+", "-", s)
    return s or "project"


def _derive_project_name(action: str, prompt: str, project_name: str | None) -> str:
    """Derives a clean project name from input parameters."""
    if project_name and project_name.strip():
        return _sanitize_name(project_name)

    # Detect common keywords from prompt
    p = (prompt or "").lower()
    if "login" in p or "signin" in p or "auth" in p:
        return "login-page"
    elif "dashboard" in p:
        return "analytics-dashboard"
    elif "portfolio" in p:
        return "portfolio-site"
    elif "todo" in p:
        return "todo-app"
    elif "weather" in p:
        return "weather-app"
    elif "calculator" in p:
        return "calculator-app"
    elif "ecommerce" in p or "shop" in p:
        return "ecommerce-store"

    # Default fallback
    words = p.split()[:3]
    if words:
        return _sanitize_name("-".join(words))
    return f"project-{int(time.time()) % 10000}"


# ── Built-in High-End Templates ───────────────────────────────────────────────

def _get_login_page_files() -> dict[str, str]:
    """Generates an ultra-premium, modern glassmorphism login & signup portal."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nexus — Secure Login</title>
  <link rel="stylesheet" href="style.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
  <div class="background-mesh">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
  </div>

  <main class="login-container">
    <div class="glass-card">
      <header class="card-header">
        <div class="brand-badge">
          <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
          <span class="brand-name">NEXUS</span>
        </div>
        <h1 class="auth-title" id="form-title">Welcome Back</h1>
        <p class="auth-subtitle" id="form-subtitle">Enter your credentials to access your console</p>
      </header>

      <div class="tabs-nav">
        <button class="tab-btn active" id="tab-signin" type="button">Sign In</button>
        <button class="tab-btn" id="tab-signup" type="button">Create Account</button>
      </div>

      <form id="auth-form" class="auth-form" novalidate>
        <div class="input-group" id="name-group" style="display: none;">
          <label for="fullname">Full Name</label>
          <div class="input-wrapper">
            <input type="text" id="fullname" placeholder="Tony Stark" autocomplete="name" />
            <span class="input-glow"></span>
          </div>
        </div>

        <div class="input-group">
          <label for="email">Email Address</label>
          <div class="input-wrapper">
            <input type="email" id="email" placeholder="tony@starkindustries.com" required autocomplete="email" />
            <span class="input-glow"></span>
          </div>
        </div>

        <div class="input-group">
          <div class="label-row">
            <label for="password">Password</label>
            <a href="#" class="forgot-link" id="forgot-pass-btn">Forgot password?</a>
          </div>
          <div class="input-wrapper">
            <input type="password" id="password" placeholder="••••••••••••" required autocomplete="current-password" />
            <button type="button" class="eye-toggle" id="toggle-password" aria-label="Toggle password visibility">
              <svg class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
            <span class="input-glow"></span>
          </div>
        </div>

        <div class="options-row" id="remember-row">
          <label class="checkbox-container">
            <input type="checkbox" id="remember" checked />
            <span class="custom-checkbox"></span>
            <span class="checkbox-label">Keep me signed in for 30 days</span>
          </label>
        </div>

        <button type="submit" class="submit-btn" id="submit-btn">
          <span class="btn-text">Authenticate</span>
          <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </button>
      </form>

      <div class="divider">
        <span>or continue with</span>
      </div>

      <div class="social-auth">
        <button class="social-btn" type="button" id="auth-google">
          <svg viewBox="0 0 24 24" class="social-icon">
            <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.9C6.2 7.3 8.9 5 12 5z"/>
            <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"/>
            <path fill="#FBBC05" d="M5.3 14.7c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.6 7.2C.6 9.2 0 11.5 0 14s.6 4.8 1.6 6.8l3.7-2.9z"/>
            <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.8-2.3-6.7-5.3L1.6 16c1.9 3.8 5.8 7 10.4 7z"/>
          </svg>
          Google
        </button>

        <button class="social-btn" type="button" id="auth-github">
          <svg viewBox="0 0 24 24" fill="currentColor" class="social-icon">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
          GitHub
        </button>
      </div>

      <footer class="card-footer">
        <p class="terms-text">Protected by end-to-end hardware encryption.</p>
      </footer>
    </div>
  </main>

  <div id="toast" class="toast" role="alert"></div>

  <script src="app.js"></script>
</body>
</html>
"""

    css_content = """/* Modern Glassmorphism Design System */
:root {
  --bg-dark: #07090e;
  --card-bg: rgba(16, 22, 34, 0.7);
  --card-border: rgba(255, 255, 255, 0.08);
  --primary: #00e5ff;
  --primary-glow: rgba(0, 229, 255, 0.35);
  --accent: #8b5cf6;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --input-bg: rgba(255, 255, 255, 0.03);
  --input-border: rgba(255, 255, 255, 0.1);
  --error: #f43f5e;
  --success: #10b981;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

body {
  background-color: var(--bg-dark);
  color: var(--text-main);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow-x: hidden;
  position: relative;
  padding: 24px;
}

/* Background animated glow orbs */
.background-mesh {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.45;
  animation: floatOrb 20s infinite alternate ease-in-out;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--primary) 0%, transparent 70%);
  top: -100px;
  left: -100px;
}

.orb-2 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
  bottom: -150px;
  right: -150px;
  animation-duration: 25s;
}

.orb-3 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, #3b82f6 0%, transparent 70%);
  top: 40%;
  right: 20%;
  animation-duration: 18s;
}

@keyframes floatOrb {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(60px, 40px) scale(1.1); }
}

/* Glass Card */
.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 460px;
}

.glass-card {
  background: var(--card-bg);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--card-border);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 40px rgba(0, 229, 255, 0.05);
  animation: cardFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cardFadeIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Header */
.card-header {
  text-align: center;
  margin-bottom: 24px;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 229, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.2);
  padding: 6px 14px;
  border-radius: 100px;
  margin-bottom: 16px;
}

.brand-icon {
  width: 18px;
  height: 18px;
  color: var(--primary);
}

.brand-name {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--primary);
}

.auth-title {
  font-size: 1.85rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #fff;
  margin-bottom: 6px;
}

.auth-subtitle {
  font-size: 0.9rem;
  color: var(--text-muted);
}

/* Tab Switcher */
.tabs-nav {
  display: flex;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 24px;
}

.tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
  padding: 9px;
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.25s ease;
}

.tab-btn.active {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

/* Form inputs */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.input-group label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-main);
  margin-bottom: 6px;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.forgot-link {
  font-size: 0.8rem;
  color: var(--primary);
  text-decoration: none;
  transition: color 0.2s;
}

.forgot-link:hover {
  text-decoration: underline;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 0.95rem;
  color: #fff;
  outline: none;
  transition: all 0.25s ease;
}

.input-wrapper input:focus {
  border-color: var(--primary);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: 0 0 0 3px var(--primary-glow);
}

.eye-toggle {
  position: absolute;
  right: 14px;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  transition: color 0.2s;
}

.eye-toggle:hover {
  color: #fff;
}

.eye-icon {
  width: 18px;
  height: 18px;
}

/* Checkbox */
.options-row {
  display: flex;
  align-items: center;
}

.checkbox-container {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.checkbox-container input {
  display: none;
}

.custom-checkbox {
  width: 18px;
  height: 18px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  background: var(--input-bg);
  display: inline-block;
  position: relative;
  transition: all 0.2s;
}

.checkbox-container input:checked + .custom-checkbox {
  background: var(--primary);
  border-color: var(--primary);
}

.checkbox-container input:checked + .custom-checkbox::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 2px;
  width: 4px;
  height: 8px;
  border: solid #000;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* Submit Button */
.submit-btn {
  margin-top: 8px;
  background: linear-gradient(135deg, var(--primary) 0%, #00b4d8 100%);
  color: #050811;
  font-size: 0.95rem;
  font-weight: 700;
  border: none;
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 8px 20px -4px var(--primary-glow);
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 25px -4px var(--primary-glow);
  filter: brightness(1.08);
}

.submit-btn:active {
  transform: translateY(0);
}

.arrow-icon {
  width: 18px;
  height: 18px;
  transition: transform 0.2s;
}

.submit-btn:hover .arrow-icon {
  transform: translateX(4px);
}

/* Divider */
.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 24px 0 18px;
}

.divider::before, .divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.divider span {
  padding: 0 12px;
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Social buttons */
.social-auth {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.social-btn {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
  border-radius: 12px;
  padding: 10px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.social-btn:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.16);
  transform: translateY(-1px);
}

.social-icon {
  width: 18px;
  height: 18px;
}

/* Footer */
.card-footer {
  text-align: center;
  margin-top: 24px;
}

.terms-text {
  font-size: 0.75rem;
  color: var(--text-muted);
  opacity: 0.7;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%) translateY(100px);
  background: rgba(16, 22, 34, 0.95);
  border: 1px solid rgba(0, 229, 255, 0.4);
  color: #fff;
  padding: 12px 24px;
  border-radius: 100px;
  font-size: 0.85rem;
  font-weight: 500;
  backdrop-filter: blur(12px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s;
  opacity: 0;
  pointer-events: none;
  z-index: 100;
}

.toast.show {
  transform: translateX(-50%) translateY(0);
  opacity: 1;
}

.toast.error {
  border-color: var(--error);
  color: var(--error);
}
"""

    js_content = """// Interactive Logic for Nexus Auth Portal
document.addEventListener('DOMContentLoaded', () => {
  const tabSignIn = document.getElementById('tab-signin');
  const tabSignUp = document.getElementById('tab-signup');
  const formTitle = document.getElementById('form-title');
  const formSubtitle = document.getElementById('form-subtitle');
  const nameGroup = document.getElementById('name-group');
  const rememberRow = document.getElementById('remember-row');
  const submitBtn = document.getElementById('submit-btn');
  const btnText = submitBtn.querySelector('.btn-text');
  const authForm = document.getElementById('auth-form');
  const togglePassBtn = document.getElementById('toggle-password');
  const passwordInput = document.getElementById('password');
  const toast = document.getElementById('toast');

  let mode = 'signin'; // 'signin' | 'signup'

  // Tab switching
  tabSignIn.addEventListener('click', () => setMode('signin'));
  tabSignUp.addEventListener('click', () => setMode('signup'));

  function setMode(newMode) {
    mode = newMode;
    if (mode === 'signin') {
      tabSignIn.classList.add('active');
      tabSignUp.classList.remove('active');
      formTitle.textContent = 'Welcome Back';
      formSubtitle.textContent = 'Enter your credentials to access your console';
      nameGroup.style.display = 'none';
      rememberRow.style.display = 'flex';
      btnText.textContent = 'Authenticate';
    } else {
      tabSignUp.classList.add('active');
      tabSignIn.classList.remove('active');
      formTitle.textContent = 'Create Account';
      formSubtitle.textContent = 'Set up your secure credentials in seconds';
      nameGroup.style.display = 'block';
      rememberRow.style.display = 'none';
      btnText.textContent = 'Deploy Identity';
    }
  }

  // Password visibility toggle
  togglePassBtn.addEventListener('click', () => {
    const isPass = passwordInput.getAttribute('type') === 'password';
    passwordInput.setAttribute('type', isPass ? 'text' : 'password');
    togglePassBtn.style.color = isPass ? 'var(--primary)' : 'var(--text-muted)';
  });

  // Form submission
  authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const pass = passwordInput.value;

    if (!email || !pass) {
      showToast('Please fill in all required credentials.', true);
      return;
    }

    btnText.textContent = mode === 'signin' ? 'Authenticating...' : 'Registering...';
    submitBtn.style.opacity = '0.7';
    submitBtn.disabled = true;

    setTimeout(() => {
      btnText.textContent = mode === 'signin' ? 'Authenticate' : 'Deploy Identity';
      submitBtn.style.opacity = '1';
      submitBtn.disabled = false;
      showToast(mode === 'signin' ? 'Access Granted. Welcome back, Commander.' : 'Account created successfully.');
    }, 1200);
  });

  // Social Auth mock handlers
  document.getElementById('auth-google').addEventListener('click', () => {
    showToast('Connecting to Google OAuth...');
  });
  document.getElementById('auth-github').addEventListener('click', () => {
    showToast('Connecting to GitHub Secure Auth...');
  });
  document.getElementById('forgot-pass-btn').addEventListener('click', (e) => {
    e.preventDefault();
    showToast('Password recovery link dispatched to your email.');
  });

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.className = `toast show ${isError ? 'error' : ''}`;
    setTimeout(() => {
      toast.className = 'toast';
    }, 3500);
  }
});
"""

    readme_content = """# Nexus Modern Login Portal

Built autonomously by **JARVIS** & **Google Antigravity IDE**.

## Features
- Glassmorphism dark aesthetic with neon blue/violet mesh backdrop.
- Interactive tab switcher between **Sign In** and **Create Account**.
- Real-time client validation and interactive password toggle.
- Single Sign-On mock hooks for Google and GitHub.
- 100% responsive for desktop and mobile displays.

## Development with Antigravity
Open this project folder in Antigravity IDE to add backend routes (e.g., Firebase, Supabase, or FastAPI).
"""

    return {
        "index.html": html_content,
        "style.css": css_content,
        "app.js": js_content,
        "README.md": readme_content,
    }


def _get_generic_web_files(title: str, prompt: str) -> dict[str, str]:
    """Generates standard starter files for a generic web application."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="style.css">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body>
  <div class="container">
    <header class="hero">
      <span class="badge">Created by JARVIS & Antigravity</span>
      <h1>{title}</h1>
      <p class="description">{prompt or 'A modern web application scaffolded and ready for development.'}</p>
    </header>

    <main class="content-panel">
      <div class="card">
        <h2>Workspace Ready</h2>
        <p>This project has been configured in your local workspace and opened in Antigravity IDE.</p>
        <button id="action-btn" class="primary-btn">Interactive Test</button>
        <p id="status-msg" class="status"></p>
      </div>
    </main>
  </div>
  <script src="app.js"></script>
</body>
</html>
"""

    css_content = """:root {
  --bg: #0b0f19;
  --card: #131b2e;
  --border: rgba(255, 255, 255, 0.1);
  --primary: #00e5ff;
  --text: #f8fafc;
  --muted: #94a3b8;
}

* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
.container { max-width: 600px; width: 100%; text-align: center; }
.badge { background: rgba(0, 229, 255, 0.1); color: var(--primary); padding: 4px 12px; border-radius: 100px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(0, 229, 255, 0.3); }
h1 { font-size: 2.2rem; margin: 16px 0 8px; color: #fff; }
.description { color: var(--muted); margin-bottom: 30px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
.card h2 { margin-bottom: 10px; font-size: 1.3rem; }
.card p { color: var(--muted); margin-bottom: 20px; font-size: 0.95rem; }
.primary-btn { background: var(--primary); color: #000; border: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; cursor: pointer; transition: transform 0.2s; }
.primary-btn:hover { transform: scale(1.05); }
.status { margin-top: 15px; color: var(--primary); font-weight: 600; min-height: 24px; }
"""

    js_content = """document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('action-btn');
  const msg = document.getElementById('status-msg');
  let clicks = 0;
  btn.addEventListener('click', () => {
    clicks++;
    msg.textContent = `Interaction verified! Click count: ${clicks}`;
  });
});
"""

    return {
        "index.html": html_content,
        "style.css": css_content,
        "app.js": js_content,
        "README.md": f"# {title}\n\n{prompt}\n\nScaffolded by JARVIS for Antigravity IDE.",
    }


def _get_python_files(title: str, prompt: str) -> dict[str, str]:
    """Generates starter files for a Python project."""
    main_py = f'''"""
{title}
Prompt: {prompt}
Scaffolded by JARVIS for Antigravity IDE.
"""

def main():
    print("========================================")
    print("🚀 {title} - Started")
    print("========================================")
    print("Workspace loaded in Google Antigravity.")

if __name__ == "__main__":
    main()
'''
    return {
        "main.py": main_py,
        "requirements.txt": "# Add your project dependencies here\n",
        "README.md": f"# {title}\n\n{prompt}\n\nRun with: `python main.py`\n",
    }


# ── Execution Logic ───────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Main entrypoint called by JARVIS plugin loader.
    """
    action = (parameters.get("action") or "create_project").strip().lower()
    project_name = parameters.get("project_name") or ""
    project_type = (parameters.get("project_type") or "auto").strip().lower()
    prompt = parameters.get("prompt") or ""
    open_browser = parameters.get("open_browser", True)

    def log(msg: str):
        safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
        try:
            print(f"[DevController] {safe_msg}")
        except Exception:
            pass
        if player and hasattr(player, "write_log"):
            try:
                player.write_log(f"DEV: {safe_msg}")
            except Exception:
                pass

    log(f"Received action='{action}', project='{project_name}', prompt='{prompt}'")

    ide_bin = _find_antigravity_ide()
    if not ide_bin:
        log("[WARN] Antigravity IDE executable not found in PATH or standard directories.")

    # ── Action 1: Create Project ──────────────────────────────────────────────
    if action in ("create_project", "build", "create", "new"):
        clean_name = _derive_project_name(action, prompt, project_name)
        project_dir = PROJECTS_DIR / clean_name

        # Avoid overwriting: add suffix if exists
        counter = 1
        base_dir_path = project_dir
        while project_dir.exists() and any(project_dir.iterdir()):
            counter += 1
            project_dir = PROJECTS_DIR / f"{clean_name}-{counter}"

        project_dir.mkdir(parents=True, exist_ok=True)
        log(f"[DIR] Created project directory at {project_dir}")

        # Choose template
        p_lower = (prompt + " " + clean_name).lower()
        is_login = "login" in p_lower or "auth" in p_lower or "signin" in p_lower
        is_python = project_type == "python" or ("python" in p_lower and not is_login)

        entry_file: Optional[Path] = None

        if is_python:
            files = _get_python_files(clean_name.replace("-", " ").title(), prompt)
            entry_file = project_dir / "main.py"
        elif is_login:
            files = _get_login_page_files()
            entry_file = project_dir / "index.html"
        else:
            files = _get_generic_web_files(clean_name.replace("-", " ").title(), prompt)
            entry_file = project_dir / "index.html"

        # Write files
        for filename, content in files.items():
            file_path = project_dir / filename
            file_path.write_text(content, encoding="utf-8")
            log(f"  [FILE] Created {filename}")

        # Add .agents/rules.md for Antigravity IDE agent
        agents_dir = project_dir / ".agents"
        agents_dir.mkdir(exist_ok=True)
        rules_content = f"""# Project Rules for Antigravity Agent
Project: {clean_name}
Goal: {prompt or 'Develop modern, robust application features.'}

Guidelines:
- Maintain clean, modern, accessible code.
- Test changes in browser or CLI before finalizing.
"""
        (agents_dir / "rules.md").write_text(rules_content, encoding="utf-8")

        # Open in Antigravity IDE
        ide_opened = False
        if ide_bin:
            try:
                # Launch Antigravity IDE with the project directory and the entry file
                target_args = [ide_bin, str(project_dir)]
                if entry_file and entry_file.exists():
                    target_args.append(str(entry_file))
                subprocess.Popen(target_args, shell=True)
                ide_opened = True
                log(f"[IDE] Launched Antigravity IDE for {project_dir}")
            except Exception as e:
                log(f"[WARN] Failed to launch Antigravity IDE: {e}")

        # Open browser preview if requested
        browser_opened = False
        if open_browser and entry_file and entry_file.suffix.lower() == ".html":
            try:
                webbrowser.open(entry_file.as_uri())
                browser_opened = True
                log("[PREVIEW] Opened live preview in browser.")
            except Exception as e:
                log(f"[WARN] Browser open failed: {e}")

        # Dispatch prompt to Antigravity Agent in background if provided
        if ide_bin and prompt and len(prompt) > 5:
            def _trigger_chat():
                time.sleep(2.5)  # Wait for IDE window to initialize
                try:
                    subprocess.Popen(
                        [ide_bin, "chat", "-m", "agent", prompt],
                        cwd=str(project_dir),
                        shell=True,
                    )
                except Exception:
                    pass
            threading.Thread(target=_trigger_chat, daemon=True).start()

        # Build response message
        details = []
        if ide_opened:
            details.append("opened Antigravity IDE")
        if browser_opened:
            details.append("launched the live preview in your browser")

        status_suffix = f" and {', '.join(details)}" if details else ""
        return (
            f"Sir, I have created the {clean_name} project in {project_dir}, "
            f"generated the complete responsive code{status_suffix}."
        )

    # ── Action 2: Open IDE ────────────────────────────────────────────────────
    elif action in ("open_ide", "open"):
        target_dir = project_name and (PROJECTS_DIR / _sanitize_name(project_name))
        target_path = str(target_dir if target_dir and target_dir.exists() else PROJECTS_DIR)

        if not ide_bin:
            return "Sir, Antigravity IDE executable was not found on your system."

        try:
            subprocess.Popen([ide_bin, target_path], shell=True)
            return f"Opened Antigravity IDE at {target_path}, sir."
        except Exception as e:
            return f"Failed to open Antigravity IDE: {e}"

    # ── Action 3: Prompt Agent ────────────────────────────────────────────────
    elif action in ("prompt_agent", "chat"):
        if not prompt:
            return "Sir, please specify what task you would like the Antigravity agent to perform."
        if not ide_bin:
            return "Sir, Antigravity IDE is required to run the agent chat."

        target_dir = project_name and (PROJECTS_DIR / _sanitize_name(project_name))
        working_dir = str(target_dir if target_dir and target_dir.exists() else PROJECTS_DIR)

        try:
            subprocess.Popen(
                [ide_bin, "chat", "-m", "agent", prompt],
                cwd=working_dir,
                shell=True,
            )
            return f"Task dispatched to Antigravity agent in {working_dir}: '{prompt}'."
        except Exception as e:
            return f"Failed to dispatch task to Antigravity agent: {e}"

    # ── Action 4: Preview ─────────────────────────────────────────────────────
    elif action in ("preview", "run"):
        target_dir = PROJECTS_DIR / _sanitize_name(project_name or "login-page")
        index_file = target_dir / "index.html"
        if index_file.exists():
            webbrowser.open(index_file.as_uri())
            return f"Launched live browser preview for {target_dir.name}, sir."
        return f"Could not find an index.html file to preview in {target_dir}."

    return f"Unknown action '{action}' for software_dev_controller."
