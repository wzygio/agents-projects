// src/web_dashboard/static/js/components/layout/Terminal.js
const { useRef, useEffect: useTerminalEffect } = React; // 重命名避免冲突

window.Terminal = ({ stepStates, focusedStepId }) => {
    const logsEndRef = useRef(null);
    const activeStep = window.PIPELINE_STEPS.find(s => s.id === focusedStepId) || window.PIPELINE_STEPS[0];
    const logs = stepStates[focusedStepId]?.logs || [];

    useTerminalEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    return (
        <div className="flex-1 pb-10 flex flex-col relative">
            <div className="terminal-wrapper">
                <div className="terminal-header">
                    <div className="window-dots">
                        <div className="mac-btn btn-red"></div>
                        <div className="mac-btn btn-yellow"></div>
                        <div className="mac-btn btn-green"></div>
                    </div>
                    <div className="ml-4 text-xs text-zinc-500 font-mono font-bold flex-1 text-center pr-12 truncate">
                        process_monitor — {activeStep.name}
                    </div>
                </div>
                <div className="terminal-body custom-scrollbar">
                    {logs.length === 0 && (
                        <div className="text-zinc-600 mt-20 text-center opacity-50">
                            <p>$ waiting for execution...</p>
                        </div>
                    )}
                    {logs.map((log, i) => {
                        let style = "text-zinc-400";
                        if (log.includes("开始")) style = "text-blue-400 font-bold mt-2 border-b border-zinc-700 pb-1";
                        if (log.includes("✅")) style = "text-emerald-400 font-bold";
                        if (log.includes("❌")) style = "text-red-400 font-bold";
                        if (log.includes("waiting")) style = "text-amber-400 font-bold animate-pulse";
                        
                        return <div key={i} className={`mb-1 break-words font-mono text-xs ${style}`}>{!log.includes("开始") && "$ "}{log}</div>
                    })}
                    <div ref={logsEndRef} />
                </div>
            </div>
        </div>
    );
};