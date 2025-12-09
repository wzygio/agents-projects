// src/web_dashboard/static/js/dashboard.js
const { useState, useEffect, useRef, useMemo } = React;

const Icon = ({ name, size = 20, className = "" }) => {
    const iconContainerRef = useRef(null);
    useEffect(() => {
        if (!iconContainerRef.current || !window.lucide) return;
        iconContainerRef.current.innerHTML = '';
        const tempIcon = document.createElement('i');
        tempIcon.setAttribute('data-lucide', name);
        iconContainerRef.current.appendChild(tempIcon);
        window.lucide.createIcons({
            root: iconContainerRef.current,
            nameAttr: 'data-lucide',
            attrs: { class: className, width: size, height: size }
        });
    }, [name, size, className]);
    return <span ref={iconContainerRef} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }} />;
};

const ArtifactCapsule = ({ result }) => {
    if (!result) return null;
    const isFile = result.type === 'file';
    const iconName = isFile ? 'download' : 'external-link';
    const className = `artifact-capsule type-${result.type}`;
    return (
        <a href={result.url} target="_blank" className={className} onClick={(e) => e.stopPropagation()}>
            <span className="capsule-icon-wrapper"><Icon name={iconName} size={14} /></span>
            <span>{result.label}</span>
        </a>
    );
};

const TASK_STRUCTURE = {
    monitor: {
        title: "Anomaly Monitor",
        nodes: [
            { type: 'single', name: "数据读取 (Spotfire/Local)" },
            { type: 'single', name: "异常识别 (AI分析)" },
            { type: 'single', name: "报告生成 (Summary)" },
            { 
                type: 'group', 
                name: "报告处理与分发", 
                subSteps: ["添加到HL记录表", "添加到异常管理表", "邮件通知责任人"]
            }
        ]
    },
    daily_report: {
        title: "Daily Report RPA",
        nodes: [
            { type: 'single', name: "生产报表下载" },
            { 
                type: 'group', 
                name: "AI 智能日报生成", 
                subSteps: ["PPT日报 (入库良率)", "Excel日报 (过货影响)"]
            },
            { 
                type: 'group', 
                name: "日报分发流程", 
                subSteps: ["归档到公盘", "截取关键指标", "发送全员邮件", "同步至Web系统"]
            }
        ]
    }
};

const INITIAL_MODULE_STATE = {
    isRunning: false,
    currentStepId: 0,
    logs: [],
    results: {},
    expandedGroups: new Set()
};

function App() {
    const [activeTab, setActiveTab] = useState('monitor');
    const [terminalState, setTerminalState] = useState('normal');
    
    // 多模块独立状态
    const [moduleStates, setModuleStates] = useState({
        monitor: { ...INITIAL_MODULE_STATE, logs: [], results: {}, expandedGroups: new Set() },
        daily_report: { ...INITIAL_MODULE_STATE, logs: [], results: {}, expandedGroups: new Set() }
    });

    const logsEndRef = useRef(null);
    const currentData = moduleStates[activeTab];

    const processedNodes = useMemo(() => {
        const rawNodes = TASK_STRUCTURE[activeTab].nodes;
        let counter = 1;
        return rawNodes.map(node => {
            if (node.type === 'single') {
                const id = counter++;
                return { ...node, startId: id, endId: id };
            } else {
                const start = counter;
                const end = counter + node.subSteps.length - 1;
                counter += node.subSteps.length;
                return { ...node, startId: start, endId: end };
            }
        });
    }, [activeTab]);

    const updateModule = (tabName, updater) => {
        setModuleStates(prev => ({
            ...prev,
            [tabName]: updater(prev[tabName])
        }));
    };

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [currentData.logs]);

    // 自动折叠逻辑
    useEffect(() => {
        const { isRunning, currentStepId } = currentData;
        if (!isRunning && currentStepId === 0) return;

        updateModule(activeTab, (prev) => {
            const newSet = new Set(prev.expandedGroups);
            let hasChanged = false;
            processedNodes.forEach(node => {
                if (node.type === 'group') {
                    const isActive = currentStepId >= node.startId && currentStepId <= node.endId;
                    const isCompleted = currentStepId > node.endId || currentStepId === 100;
                    if (isActive && !newSet.has(node.startId)) {
                        newSet.add(node.startId);
                        hasChanged = true;
                    }
                    if (isCompleted && !isActive && newSet.has(node.startId)) {
                        newSet.delete(node.startId);
                        hasChanged = true;
                    }
                }
            });
            return hasChanged ? { ...prev, expandedGroups: newSet } : prev;
        });
    }, [currentData.currentStepId, currentData.isRunning, activeTab, processedNodes]);

    const toggleGroup = (startId) => {
        updateModule(activeTab, (prev) => {
            const newSet = new Set(prev.expandedGroups);
            if (newSet.has(startId)) newSet.delete(startId);
            else newSet.add(startId);
            return { ...prev, expandedGroups: newSet };
        });
    };

    // 启动流程
    const startProcess = async (targetTab) => {
        // 1. 初始化状态
        updateModule(targetTab, () => ({
            isRunning: true,
            currentStepId: 0,
            logs: [],
            results: {},
            expandedGroups: new Set()
        }));

        if (terminalState === 'minimized') setTerminalState('normal');
        
        try {
            // 【核心修复】添加时间戳参数 ?t=... 
            // 这强制浏览器将此视为一个新的独立请求，不再排队，从而实现真正的并行
            const response = await fetch(`/start/${targetTab}?t=${Date.now()}`);
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
                        
                        updateModule(targetTab, (prev) => {
                            let nextState = { ...prev };
                            if (data.status === 'done') {
                                nextState.isRunning = false;
                                nextState.currentStepId = 100;
                            } else {
                                if (data.log) nextState.logs = [...prev.logs, data.log];
                                if (data.status === 'running') nextState.currentStepId = data.step_id;
                                if (data.result && data.step_id) nextState.results = { ...prev.results, [data.step_id]: data.result };
                            }
                            return nextState;
                        });
                    } catch (e) { console.error(e); }
                }
            }
        } catch (error) {
            console.error(error);
            updateModule(targetTab, (prev) => ({ ...prev, isRunning: false, logs: [...prev.logs, "ERROR: Connection failed"] }));
        }
    };

    const handleClose = (e) => { e.stopPropagation(); updateModule(activeTab, (prev) => ({ ...prev, logs: [] })); };
    const handleMinimize = (e) => { e.stopPropagation(); setTerminalState(prev => prev === 'minimized' ? 'normal' : 'minimized'); };
    const handleMaximize = (e) => { e.stopPropagation(); setTerminalState(prev => prev === 'maximized' ? 'normal' : 'maximized'); };

    return (
        <div className="main-layout font-sans">
            <div className="sidebar">
                <div className="mb-10 px-2 mt-2">
                    <div className="h-10 w-10 bg-black rounded-full flex items-center justify-center text-white mb-4 shadow-xl shadow-black/20">
                        <Icon name="aperture" size={24} className="text-white" />
                    </div>
                    <h1 className="text-xl font-extrabold tracking-tight text-black">OLED.Auto</h1>
                    <p className="text-xs font-bold text-slate-400 mt-1 tracking-widest uppercase">Process Hub</p>
                </div>
                
                <div className="flex-1 space-y-2">
                    {Object.keys(TASK_STRUCTURE).map(key => {
                        const state = moduleStates[key];
                        return (
                            <div key={key} onClick={() => setActiveTab(key)} className={`nav-item ${activeTab === key ? 'active' : ''}`}>
                                <Icon name={key === 'monitor' ? 'activity' : 'file-bar-chart-2'} size={18} />
                                <span className="flex-1">{key === 'monitor' ? '异常监控' : '日报生成'}</span>
                                
                                {/* 【新增】侧边栏状态指示器：让并行状态可视化 */}
                                {state.isRunning ? (
                                    <div className="flex items-center gap-1.5 px-2 py-0.5 bg-green-100 rounded-full border border-green-200">
                                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                                        <span className="text-[10px] font-bold text-green-700">RUNNING</span>
                                    </div>
                                ) : state.currentStepId === 100 ? (
                                    <div className="px-2 py-0.5 bg-slate-100 rounded-full border border-slate-200">
                                        <span className="text-[10px] font-bold text-slate-500">DONE</span>
                                    </div>
                                ) : null}
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="flex-1 flex flex-col p-10 bg-[#fafafa]">
                <div className="flex justify-between items-end mb-10 pb-6 border-b border-slate-200">
                    <div>
                        <h2 className="text-4xl font-black text-black tracking-tight mb-2">{TASK_STRUCTURE[activeTab].title}</h2>
                        <p className="text-slate-600 font-medium">Enterprise automated workflow integration.</p>
                    </div>
                    <button 
                        onClick={() => startProcess(activeTab)} 
                        disabled={currentData.isRunning} 
                        className={`px-8 py-3 rounded-full font-bold text-sm transition-all flex items-center gap-2 ${currentData.isRunning ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-black text-white hover:scale-105 hover:shadow-xl shadow-black/10'}`}
                    >
                        {currentData.isRunning ? <Icon name="loader-2" className="animate-spin text-slate-400" size={16} /> : <Icon name="play" className="text-white fill-current" size={16} />}
                        {currentData.isRunning ? 'Running...' : 'Start Pipeline'}
                    </button>
                </div>

                <div className="flex-1 flex gap-16 overflow-hidden">
                    <div className="w-[560px] overflow-y-auto step-list pb-20 no-scrollbar relative">
                        {processedNodes.map((node, index) => {
                            const isGroup = node.type === 'group';
                            const stepId = currentData.currentStepId;
                            const isNodeCompleted = stepId > node.endId || stepId === 100;
                            const isNodeActive = !isNodeCompleted && (stepId >= node.startId && stepId <= node.endId);
                            const isExpanded = currentData.expandedGroups.has(node.startId);
                            let rowClass = "";
                            if (isNodeActive) rowClass = "active";
                            if (isNodeCompleted) rowClass = "completed";

                            return (
                                <div key={index} className={`node-wrapper ${rowClass}`}>
                                    <div className={`node-row ${isGroup ? 'cursor-pointer' : ''}`} onClick={() => isGroup && toggleGroup(node.startId)}>
                                        <div className="icon-circle">
                                            {isNodeCompleted ? <Icon name="check" size={22} /> : isNodeActive ? <Icon name={isGroup ? "layers" : "loader-2"} className={!isGroup ? "animate-spin" : ""} size={22} /> : <span className="text-xs font-bold">{node.startId}</span>}
                                        </div>
                                        <div className="spatial-card">
                                            <div className="flex flex-col">
                                                <div className="card-title text-base font-semibold flex items-center gap-2">
                                                    {node.name}
                                                    {isGroup && <Icon name="chevron-down" size={16} className={`text-slate-400 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} />}
                                                </div>
                                                {isGroup && isNodeActive && <div className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-full w-fit mt-1">Running</div>}
                                            </div>
                                            <ArtifactCapsule result={currentData.results[node.startId]} />
                                        </div>
                                    </div>
                                    {isGroup && (
                                        <div className={`sub-group-container ${isExpanded ? 'expanded' : ''}`}>
                                            <div className="sub-group-inner">
                                                {node.subSteps.map((subStepName, subIndex) => {
                                                    const realSubId = node.startId + subIndex;
                                                    const isSubCompleted = stepId > realSubId || stepId === 100;
                                                    const isSubActive = stepId === realSubId;
                                                    return (
                                                        <div key={subIndex} className={`sub-node-row ${isSubActive ? 'active' : ''} ${isSubCompleted ? 'completed' : ''}`} style={{transitionDelay: `${subIndex * 50}ms`}}>
                                                            <div className="branch-curve"></div>
                                                            <div className="sub-icon-circle">
                                                                {isSubActive ? <Icon name="loader-2" className="animate-spin" size={14} /> : isSubCompleted ? <Icon name="check" size={14} /> : <div className="w-1.5 h-1.5 rounded-full bg-slate-300"></div>}
                                                            </div>
                                                            <div className="sub-card">
                                                                <div className="flex flex-col">
                                                                    <span className="font-medium">{subStepName}</span>
                                                                    {isSubActive && <span className="text-xs text-blue-600 font-bold">Processing</span>}
                                                                </div>
                                                                <ArtifactCapsule result={currentData.results[realSubId]} />
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                        <div className={`node-wrapper ${currentData.currentStepId === 100 ? 'completed' : ''}`} style={{opacity: currentData.currentStepId === 100 ? 1 : 0.4, filter: currentData.currentStepId === 100 ? 'none' : 'grayscale(100%)', transition: 'all 0.5s ease'}}>
                            <div className="node-row">
                                <div className="icon-circle" style={{borderColor: currentData.currentStepId === 100 ? '#10b981' : '#e2e8f0', color: currentData.currentStepId === 100 ? '#10b981' : '#cbd5e1', backgroundColor: currentData.currentStepId === 100 ? '#ecfdf5' : '#f8fafc'}}>
                                    <Icon name="flag" size={22} className={currentData.currentStepId === 100 ? "fill-current" : ""} />
                                </div>
                                <div className="spatial-card" style={{border: 'none', background: 'transparent', boxShadow: 'none', paddingLeft: 0}}>
                                    <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                                        {currentData.currentStepId === 100 ? "Workflow Completed" : "End"}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 pb-10 flex flex-col relative">
                        <div className={`terminal-wrapper ${terminalState}`}>
                            <div className="terminal-header" onDoubleClick={handleMaximize}>
                                <div className="window-dots">
                                    <div className="mac-btn btn-red" onClick={handleClose}></div>
                                    <div className="mac-btn btn-yellow" onClick={handleMinimize}></div>
                                    <div className="mac-btn btn-green" onClick={handleMaximize}></div>
                                </div>
                                <div className="ml-4 text-xs text-zinc-500 font-mono font-bold flex-1 text-center pr-12 truncate">
                                    {/* 【新增】日志标题明确指出当前是哪个模块 */}
                                    agent_runner — {TASK_STRUCTURE[activeTab].title}
                                </div>
                            </div>
                            <div className="terminal-body">
                                {currentData.logs.length === 0 && <div className="text-zinc-600 select-none font-medium">$ system ready.<br/>$ awaiting instructions for {activeTab}...<br/><span className="animate-pulse">_</span></div>}
                                {currentData.logs.map((log, i) => {
                                    let style = "text-zinc-400"; 
                                    if (log.includes("EXEC:")) style = "text-blue-400 font-bold";
                                    else if (log.includes("OK:")) style = "text-emerald-400 font-bold";
                                    else if (log.includes("info")) style = "text-zinc-500 italic font-medium";
                                    return <div key={i} className={`mb-1 break-words ${style} font-mono text-sm`}>{!log.includes("info") && <span className="text-zinc-600 mr-2">$</span>}{log}</div>
                                })}
                                <div ref={logsEndRef} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);