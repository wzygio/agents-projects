// src/web_dashboard/static/js/dashboard.js
const { useState, useEffect } = React;

function App() {
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

        try {
            let url = `/start/automated_duty_system?mode=${runMode}`;
            if (targetStepId !== null) url += `&step_id=${targetStepId}`;

            const response = await fetch(url);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const lines = decoder.decode(value).split('\n');
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
        finally {
            setIsGlobalRunning(false);
            if (targetStepId !== null) updateStepState(targetStepId, s => ({...s, status: s.status === 'running' ? 'error' : s.status}));
        }
    };

    return (
        <div className="main-layout font-sans bg-[#fafafa]">
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

                <div className="flex-1 flex gap-16 overflow-hidden">
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