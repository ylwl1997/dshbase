#!/usr/bin/env python3
"""Fill use/aud/dev (en+zh) notes for every plugin missing a hand-written entry.

Category-level templates keep every plugin detail page complete, while the
hand-written entries in plugin-notes.json stay as higher-quality overrides.
Re-runnable: only plugins still missing a note get a template.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')
NOTES = os.path.join(ROOT, 'src', 'data', 'plugin-notes.json')

# Category -> {use, aud, dev, use_zh, aud_zh, dev_zh}
TEMPLATES = {
    'Developer': {
        'use': "Extend the agent's coding surface — give it a new tool, workflow, or integration so it handles a dev task it couldn't before.",
        'aud': 'Developers who want dsh to behave like a teammate on real codebases — editing, running, and verifying changes rather than just answering.',
        'dev': "The tool/command surface is the seam: expose more of the SDK, add smarter context wiring, or tighten the loop between code changes and verification.",
        'use_zh': '扩展 agent 的编码能力面——给它一个新工具、工作流或集成，让它接手以前做不了的开发任务。',
        'aud_zh': '想让 dsh 在真实代码库上像队友一样干活的开发者——能改、能跑、能验证，而不只是回答问题。',
        'dev_zh': '工具/命令面就是缝：暴露更多 SDK 能力、加更聪明的上下文接线，或收紧改代码与验证之间的循环。',
    },
    'AI Models': {
        'use': 'Bring a new model, provider, or routing policy into the loop so dsh can pick the right brain for the job.',
        'aud': 'Users juggling multiple models or providers who want cost, quality, and latency balanced automatically.',
        'dev': 'Provider adapters and routing heuristics are the seams — add a backend, tune the fallback chain, or add per-task model selection.',
        'use_zh': '把一个新模型、provider 或路由策略接入循环，让 dsh 能为任务选对脑子。',
        'aud_zh': '同时用多个模型或 provider、想让成本/质量/延迟自动平衡的人。',
        'dev_zh': 'provider 适配器和路由启发式是缝——加后端、调回退链，或加按任务的模型选择。',
    },
    'UI & Skins': {
        'use': 'Change how dsh looks or how you interact with it — a theme, a skin, or a new panel that reshapes the workspace.',
        'aud': 'Users who spend hours in the web UI and want it to look and feel the way they work.',
        'dev': 'Skins, panels, and theme tokens are the extension points — author a new skin, add a panel, or sync tokens with an upstream palette.',
        'use_zh': '改变 dsh 的外观或交互方式——一套主题、皮肤或新面板，重塑工作区。',
        'aud_zh': '在 web UI 里一待几小时、想让它按自己的习惯好看又好用的人。',
        'dev_zh': '皮肤、面板和主题 token 是扩展点——写新皮肤、加面板，或与上游配色同步 token。',
    },
    'Knowledge': {
        'use': 'Give the agent a memory, a knowledge base, or a retrieval layer so it stops forgetting context between sessions.',
        'aud': 'Users running long projects who want the agent to remember decisions, docs, and preferences without re-explaining.',
        'dev': 'The memory/retrieval backend is the seam — plug a new store, tune what gets distilled, or add citation and audit trails.',
        'use_zh': '给 agent 一套记忆、知识库或检索层，让它不再跨会话丢上下文。',
        'aud_zh': '跑长项目、想让 agent 记住决策、文档和偏好而不用每次重讲的人。',
        'dev_zh': '记忆/检索后端是缝——插新存储、调蒸馏策略，或加引用与审计轨迹。',
    },
    'Desktop': {
        'use': 'Run dsh as a native desktop app — its own window, tray icon, and shortcuts — instead of a browser tab.',
        'aud': 'Users who want an installed-app feel and system integration (tray, global hotkeys, auto-launch) on their OS.',
        'dev': 'The native shell is the seam — add global shortcuts, notifications, single-instance locking, or OS-specific behaviors.',
        'use_zh': '把 dsh 跑成原生桌面应用——独立窗口、托盘图标、快捷键——而不是浏览器标签。',
        'aud_zh': '想要已安装应用的感觉和系统集成（托盘、全局热键、开机自启）的人。',
        'dev_zh': '原生壳是缝——加全局快捷键、通知、单实例锁或按 OS 定制的行为。',
    },
    'Automation': {
        'use': 'Automate a repetitive job — scheduling, chaining tasks, or reacting to events — so it runs without you starting it.',
        'aud': 'Users with recurring work who want it cron-style and hands-off rather than manually triggered.',
        'dev': 'Triggers and task templates are the seams — add event-driven or file-watch triggers, and richer workflow composition.',
        'use_zh': '自动化一项重复工作——调度、串联任务或响应事件——不用你亲手启动。',
        'aud_zh': '有周期性工作、想 cron 式无人值守而非手动触发的人。',
        'dev_zh': '触发器和任务模板是缝——加事件驱动或文件监听触发，以及更丰富的流程编排。',
    },
    'Network': {
        'use': "Give the agent network access — requests, APIs, proxies, or protocols — so it can reach external systems.",
        'aud': 'Users whose tasks touch the network — calling APIs, fetching resources, or talking to remote services.',
        'dev': 'Adapters and request shaping are the seams — add protocols, auth handlers, retries, and endpoint abstractions.',
        'use_zh': '给 agent 网络能力——请求、API、代理或协议——让它能触达外部系统。',
        'aud_zh': '任务涉及网络的人——调 API、抓资源或与远端服务通信。',
        'dev_zh': '适配器和请求整形是缝——加协议、鉴权处理器、重试和端点抽象。',
    },
    'Browser': {
        'use': 'Let the agent drive a real browser — navigate, click, fill, and read pages — for research or UI testing.',
        'aud': 'Users who want browser automation done by the agent rather than a separate scraper or test script.',
        'dev': 'Browser actions are the seam — expose more tool calls (form fill, downloads, tab management) to the model.',
        'use_zh': '让 agent 驱动真实浏览器——导航、点击、填表、读页面——做调研或 UI 测试。',
        'aud_zh': '想让浏览器自动化交给 agent、而非另写爬虫或测试脚本的人。',
        'dev_zh': '浏览器动作是缝——把更多工具调用（填表、下载、标签管理）暴露给模型。',
    },
    'Terminal': {
        'use': "Improve the terminal experience — a TUI, command palette, or shell integration — so dsh feels native in a terminal.",
        'aud': 'Terminal-first developers who drive dsh from the command line and want it to behave like the CLI agents they know.',
        'dev': 'The TUI layout and shell integration are the seams — add panels, keybindings, or new shell hooks.',
        'use_zh': '改善终端体验——TUI、命令面板或 shell 集成——让 dsh 在终端里如原生一般。',
        'aud_zh': '终端优先、从命令行驱动 dsh、想让它像熟悉的 CLI agent 一样工作的开发者。',
        'dev_zh': 'TUI 布局和 shell 集成是缝——加面板、快捷键或新的 shell 钩子。',
    },
    'Storage': {
        'use': 'Give the agent durable storage — a database, file store, or persistence layer — so state survives sessions.',
        'aud': 'Users whose tasks need to read or write structured data and keep it across runs.',
        'dev': 'Storage backends and data models are the seams — plug a new database, add schemas, or expose query tools.',
        'use_zh': '给 agent 持久存储——数据库、文件存储或持久层——让状态跨会话留存。',
        'aud_zh': '任务需要读写结构化数据并跨运行保留的人。',
        'dev_zh': '存储后端和数据模型是缝——插新数据库、加 schema 或暴露查询工具。',
    },
    'Vision': {
        'use': 'Give the model eyes — image understanding, OCR, or screen grounding — so it reads visuals instead of guessing.',
        'aud': 'Users who hand the model screenshots, diagrams, or photos and want them understood natively.',
        'dev': 'Vision backends and preprocessing are the seams — add OCR, region cropping, or tune resolution and model routing.',
        'use_zh': '给模型装上眼睛——图像理解、OCR 或屏幕定位——让它读视觉而非靠猜。',
        'aud_zh': '会把截图、图表或照片交给模型、想被原生理解的人。',
        'dev_zh': '视觉后端和预处理是缝——加 OCR、区域裁剪，或调分辨率和模型路由。',
    },
    'Data': {
        'use': 'Let the agent crunch data — parse, transform, or analyze — so it works with real datasets, not just prose.',
        'aud': 'Users whose tasks involve tables, files, or numbers that need processing or analysis.',
        'dev': 'Data sources and transformation tools are the seams — add formats, aggregations, or visualization outputs.',
        'use_zh': '让 agent 处理数据——解析、转换或分析——用真实数据集工作，而不只是文字。',
        'aud_zh': '任务涉及表格、文件或数字、需要处理或分析的人。',
        'dev_zh': '数据源和转换工具是缝——加格式、聚合或可视化输出。',
    },
    'Security': {
        'use': 'Harden the agent or its workspace — scanning, sanitizing, or auditing — so untrusted content and code are caught first.',
        'aud': 'Users who care about supply-chain and prompt-injection risk and want defenses built in.',
        'dev': 'Detectors and policies are the seams — add rules, scopes, or richer audit logging for what was flagged.',
        'use_zh': '加固 agent 或其工作区——扫描、净化或审计——先拦下不可信内容和代码。',
        'aud_zh': '在意供应链和提示注入风险、想要内置防护的人。',
        'dev_zh': '检测器和策略是缝——加规则、作用域或更丰富的被标记项审计日志。',
    },
    'Productivity': {
        'use': "Connect dsh to the tools you actually work in — office docs, task boards, or chat apps — so it fits your workflow.",
        'aud': 'Users who want the agent to operate inside their existing productivity stack instead of a silo.',
        'dev': 'Integrations and adapters are the seams — add a new app connector, richer read/write, or workflow triggers.',
        'use_zh': '把 dsh 接进你真正在用的工具——办公文档、任务板或聊天软件——让它融入你的工作流。',
        'aud_zh': '想让 agent 在既有生产力工具栈里干活、而非被隔离在孤岛的人。',
        'dev_zh': '集成和适配器是缝——加新的应用连接器、更丰富的读写或工作流触发。',
    },
    'Content': {
        'use': 'Turn the agent into a writer — generating, editing, or localizing text and media — for content-heavy tasks.',
        'aud': 'Users producing docs, posts, or marketing copy who want the agent to draft and revise in the same loop.',
        'dev': 'Content pipelines and format outputs are the seams — add templates, style rules, or export targets.',
        'use_zh': '把 agent 变成写手——生成、编辑或本地化文本与媒体——用于内容密集任务。',
        'aud_zh': '产出文档、帖子或营销文案、想让 agent 在同一循环里起草和修改的人。',
        'dev_zh': '内容流水线和格式输出是缝——加模板、风格规则或导出目标。',
    },
}


def main():
    with open(DB, encoding='utf-8') as f:
        db = json.load(f)
    with open(NOTES, encoding='utf-8') as f:
        notes = json.load(f)

    added = 0
    skipped_cat = []
    for cat, items in db.items():
        tpl = TEMPLATES.get(cat)
        for p in items:
            name = p.get('name')
            if not name or name in notes:
                continue
            if tpl is None:
                skipped_cat.append((cat, name))
                continue
            notes[name] = dict(tpl)
            added += 1

    with open(NOTES, 'w', encoding='utf-8') as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

    print(f'added {added} template notes; total {len(notes)} entries')
    if skipped_cat:
        print(f'WARNING: {len(skipped_cat)} plugins in unmapped categories:', skipped_cat[:10])


if __name__ == '__main__':
    main()
