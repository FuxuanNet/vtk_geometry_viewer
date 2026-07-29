<div align="center">

# VTK 几何与结果查看器

基于 VTK.js 的浏览器端 Legacy ASCII VTK 网格与结果查看工具。

![VTK.js](https://img.shields.io/badge/VTK.js-32.12-EF553B)
![Vite](https://img.shields.io/badge/Vite-5.4-646CFF?logo=vite)
![JavaScript](https://img.shields.io/badge/JavaScript-ES_Modules-F7DF1E?logo=javascript&logoColor=111111)
![GitHub Pages](https://img.shields.io/badge/Deploy-GitHub_Pages-222222?logo=githubpages)

</div>

---

## 项目简介

该查看器直接在浏览器中读取 Legacy ASCII `.vtk` 文件，用于检查 SAM VTKToolset 导出的网格和结果字段。文件在当前浏览器中解析和渲染，页面无需 SAM SDK。

## 主要功能

- 显示梁、杆等线单元。
- 显示三角形、四边形壳单元及实体单元外表面。
- 统计节点、单元、单元类型、边界和异常连接。
- 识别节点场与单元场。
- 按位移模长、应力、应变及分量进行结果着色。
- 显示结果颜色图例、最小值和最大值。
- 支持选择文件和拖放文件。
- 提供中文控制面板、重置视角和网格边线开关。

## 技术栈

| 技术 | 用途 |
|---|---|
| VTK.js | 三维网格与结果场渲染 |
| Vite | 本地开发和生产构建 |
| JavaScript | Legacy ASCII VTK 解析及交互逻辑 |
| GitHub Actions | 自动构建并部署 GitHub Pages |

## 本地运行

需要 Node.js 18 或更高版本，推荐使用 Node.js 20。

```powershell
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:8765
```

也可以运行项目提供的 PowerShell 启动脚本：

```powershell
.\start_viewer.ps1
```

## 使用方法

1. 点击“选择文件”，或将 `.vtk` 文件拖到页面中。
2. 使用鼠标旋转、缩放和平移模型。
3. 在“结果着色”中选择节点场或单元场。
4. 查看右上角颜色图例以及最小值、最大值。
5. 使用显示开关分别检查线单元和壳、实体表面。

网页读取的是 Legacy ASCII `.vtk`。XML `.vtu` 和二进制 VTK 文件需要先转换为受支持格式。

## 生产构建

```powershell
npm ci
npm run build
```

构建结果位于 `dist`。项目使用相对资源路径，可以部署在 GitHub Pages 的仓库子路径下。

## GitHub Pages 部署

仓库已包含 `.github/workflows/deploy-pages.yml`。上传到 GitHub 后：

1. 打开仓库的 `Settings -> Pages`。
2. 将 `Source` 设置为 `GitHub Actions`。
3. 将代码推送到 `main` 分支。
4. 等待 `Deploy VTK Viewer to GitHub Pages` 工作流完成。

首次上传示例：

```powershell
git add .
git commit -m "feat: add VTK geometry viewer"
git remote add origin https://github.com/<用户名>/<仓库名>.git
git push -u origin main
```

## 项目结构

```text
vtk_geometry_viewer/
├── .github/workflows/    GitHub Pages 自动部署
├── src/
│   ├── main.js           VTK 解析、渲染与页面交互
│   └── style.css         中文工程界面样式
├── index.html            网站入口
├── package.json          前端依赖和命令
├── vite.config.js        GitHub Pages 相对路径配置
└── start_viewer.ps1      Windows 本地启动脚本
```

## 与其他项目的关系

| 项目 | 关系 |
|---|---|
| VTKToolset | 在 SAM 中将模型和结果导出为 `.vtk` |
| VTK 几何与结果查看器 | 在浏览器中检查导出的 `.vtk` 几何与结果字段 |
| NH2SH | 将 Nastran H5 转换为 SAM 支持的数据，属于更上游的数据转换工具 |

查看器可以作为独立网站运行，不引用 VTKToolset、SAMSDK 或 NH2SH 源码。测试时只需要准备 Legacy ASCII `.vtk` 文件。

## 仓库提交规则

`.gitignore` 已排除：

- `node_modules` 和 Vite 缓存。
- `dist` 本地构建结果。
- Python 缓存和本地验证结果。
- 日志及操作系统临时文件。

`package-lock.json` 应随源码提交，GitHub Actions 会通过 `npm ci` 安装完全一致的依赖版本。

