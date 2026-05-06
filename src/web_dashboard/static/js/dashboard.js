// src/web_dashboard/static/js/dashboard.js
const { useState, useEffect } = React;

function App() {
    // 状态管理
    const [runMode, setRunMode] = useState('human');
    const [isGlobalRunning, setIsGlobalRunning] = useState(false);
    const [focusedStepId, setFocusedStepId] = useState(1);
    
    // 初始化状态
    const [stepStates, setStepStates] = useState(() => {
        const initial = {};
        window.PIPELINE_STEPS.forEach(step => initial[step.id] = { status: 'idle', logs: [], result: null });
        return initial;
    });

    const updateStepState = (id, updater) => {
        setStepStates(prev => ({ ...prev, [id]: updater(prev[id]) }));
    };

    // 核心业务逻辑 (Fetch)
    const runTask = async (targetStepId = null) => {
        // 参数：targetStepId。如果为 null，则重置所有状态并从头开始运行整个流水线；如果指定了 ID，则仅运行该步骤。
        if (targetStepId === null) {
            setIsGlobalRunning(true);
            setStepStates(prev => {
                const next = { ...prev };
                Object.keys(next).forEach(k => next[k] = { status: 'idle', logs: [], result: null });
                return next;
            });
            setFocusedStepId(1);
        } else {
            updateStepState(targetStepId, () => ({ status: 'running', logs: [], result: null }));
            setFocusedStepId(targetStepId);
        }

        // 请求准备
        try {
            let url = `/start/automated_duty_system?mode=${runMode}`;
            if (targetStepId !== null) url += `&step_id=${targetStepId}`;

            // 流式读取
            const response = await fetch(url); // 使用 fetch 发起请求
            const reader = response.body.getReader(); // 通过 response.body.getReader() 获取读取器
            const decoder = new TextDecoder(); // 使用 TextDecoder 解码二进制数据

            // 🛠️ 修复：新增缓冲区变量，用于拼接被网络截断的 JSON 碎片
            let buffer = ''; 

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                // 🛠️ 修复：追加新数据到缓冲区 (开启 stream: true 保证多字节字符不乱码)
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                
                // 🛠️ 修复：把最后一行（必定是不完整/未闭合的）弹出来，留在 buffer 里等下个 chunk
                buffer = lines.pop(); 

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'done') continue;
                        if (data.step_id) {
                            const sId = data.step_id;
                            if (targetStepId === null && data.status === 'running') {
                                setFocusedStepId(curr => (curr !== sId ? sId : curr));
                            }
                            updateStepState(sId, (prev) => {
                                let newState = { ...prev };
                                if (['running', 'completed', 'error', 'waiting_input'].includes(data.status)) {
                                     newState.status = data.status === 'waiting_input' ? 'waiting' : data.status;
                                }
                                if (data.log) newState.logs = [...prev.logs, data.log];
                                if (data.result) newState.result = data.result;
                                return newState;
                            });
                        }
                    } catch (e) { console.error(e); }
                }
            }
        } catch (err) { console.error(err); } 
        // 异常处理与请理
        finally {
            setIsGlobalRunning(false);
            if (targetStepId !== null) updateStepState(targetStepId, s => ({...s, status: s.status === 'running' ? 'error' : s.status}));
        }
    };

    // UI布局与组件
    return (
        <div className="flex h-screen w-full font-sans bg-[#fafafa]">
            {/* 侧边栏 (静态) */}
            <div className="sidebar">
                <div className="mb-10 px-2 mt-2">
                    <div className="h-10 w-10 bg-black rounded-full flex items-center justify-center text-white mb-4 shadow-xl shadow-black/20">
                        <window.Icon name="aperture" size={24} className="text-white" />
                    </div>
                    <h1 className="text-xl font-extrabold tracking-tight text-black">值班自动化系统</h1>
                    <p className="text-xs font-bold text-slate-400 mt-1 tracking-widest uppercase">PIE - 大数据科</p>
                </div>
                <div className="flex-1 space-y-2">
                    <div className="nav-item active">
                        <window.Icon name="layers" size={18} />
                        <span className="flex-1">自动化流水线</span>
                        {isGlobalRunning && <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>}
                    </div>
                </div>
            </div>

            {/* 主内容 */}
            <div className="flex-1 flex flex-col p-10 bg-[#fafafa]">
                {/* 1. Header 组件 */}
                <window.Header 
                    runMode={runMode} 
                    setRunMode={setRunMode} 
                    isGlobalRunning={isGlobalRunning} 
                    runTask={runTask} 
                />

                <div className="flex-1 flex gap-16 overflow-hidden pt-4">
                    {/* 2. StepList 组件 */}
                    <window.StepList 
                        stepStates={stepStates}
                        focusedStepId={focusedStepId}
                        setFocusedStepId={setFocusedStepId}
                        runMode={runMode}
                        isGlobalRunning={isGlobalRunning}
                        runTask={runTask}
                    />

                    {/* 3. Terminal 组件 */}
                    <window.Terminal 
                        stepStates={stepStates}
                        focusedStepId={focusedStepId}
                    />
                </div>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);