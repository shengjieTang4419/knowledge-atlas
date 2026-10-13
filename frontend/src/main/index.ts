/** Electron 主进程入口：只做窗口生命周期（业务在 Python）。 */
import { join, normalize } from 'node:path'
import { pathToFileURL } from 'node:url'

import { BrowserWindow, app, net, protocol, screen, shell } from 'electron'

import { registerIpc } from './ipc'

const isDev = !app.isPackaged

/**
 * 生产态用自定义协议 `app://` 提供渲染产物。
 *
 * 为什么不能用 `file://`（实测）：file:// 页面加载同目录的 `<script type="module">`
 * 与 CSS 会被 webSecurity 判为跨源而**全部拒绝**（performance 里 resources 为空、
 * 同步 XHR 也失败）——页面只剩空壳。官方推荐做法就是注册一个 standard+secure 的
 * 自定义协议，语义等同 http，从而无需关掉 webSecurity。
 */
const APP_SCHEME = 'app'
const APP_ORIGIN = `${APP_SCHEME}://bundle`
const RENDERER_DIR = join(__dirname, '../renderer')

protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true }
  }
])

function serveRenderer(): void {
  protocol.handle(APP_SCHEME, request => {
    const { pathname } = new URL(request.url)
    const rel = decodeURIComponent(pathname).replace(/^\/+/, '')
    const target = normalize(join(RENDERER_DIR, rel || 'index.html'))
    // 防目录穿越：解析后必须仍在渲染产物目录内
    if (!target.startsWith(RENDERER_DIR)) {
      return new Response('forbidden', { status: 403 })
    }
    return net.fetch(pathToFileURL(target).toString())
  })
}

function createWindow(): void {
  // 按「可用区」定尺寸（扣掉菜单栏与 Dock）。
  //
  // 实测根因：写死 height:1000 在 1512×982 的屏上**比可用区 885 还高** —— Electron 只能把
  // 窗口顶到工作区顶部、底边溢出到 Dock 底下/屏幕外。于是贴窗口底边 `bottom:20px` 的右下角
  // 设置入口（齿轮）就落进那条不可靠的带子里，用户「确实看不到」。
  // 尺寸自适应可用区后，窗口四角都稳定落在可见范围内。
  const { workAreaSize } = screen.getPrimaryDisplay()
  const width = Math.min(1500, workAreaSize.width - 40)
  const height = Math.min(1000, workAreaSize.height - 40)

  const win = new BrowserWindow({
    width,
    height,
    minWidth: Math.min(1024, width),
    minHeight: Math.min(680, height),
    show: false,
    autoHideMenuBar: true,
    backgroundColor: '#0b0e13',
    title: 'Knowledge Atlas',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  win.on('ready-to-show', () => win.show())

  // 外链一律交给系统浏览器，不在应用内开新窗口
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  // 开发态走 Vite devServer（HMR）；生产态走 app://
  if (isDev && process.env.ELECTRON_RENDERER_URL) {
    void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void win.loadURL(`${APP_ORIGIN}/index.html`)
  }
}

app.whenReady().then(() => {
  app.setAppUserModelId('com.tangshengjie.knowledge-atlas')
  serveRenderer()
  registerIpc()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
