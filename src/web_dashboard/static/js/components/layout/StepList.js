// src/web_dashboard/static/js/components/layout/StepList.js

window.StepList = ({ stepStates, focusedStepId, setFocusedStepId, runMode, isGlobalRunning, runTask }) => {
    return (
        // 🛠️ 修复：引入 step-list 类，增加 pt-8 (顶部边距防止裁剪)，并开启内部纵向滚动
        <div className="step-list flex flex-col gap-4 w-[480px] pt-8 h-full overflow-y-auto overflow-x-hidden scrollbar-hide">
            {window.PIPELINE_STEPS.map((step) => {
                const state = stepStates[step.id];
                const isFocused = focusedStepId === step.id;
                
                let wrapperClass = "";
                if (state.status === 'completed') wrapperClass = "completed";
                if (state.status === 'running' || state.status === 'waiting') wrapperClass = "active";

                return (
                    <div 
                        key={step.id} 
                        className={`node-wrapper ${wrapperClass}`} 
                        onClick={() => setFocusedStepId(step.id)}
                    >
                        <div className="node-row cursor-pointer">
                            <div className="icon-circle">
                                {state.status === 'completed' ? <window.Icon name="check" size={22} /> : 
                                 state.status === 'running' ? <window.Icon name="loader-2" className="animate-spin" size={22} /> :
                                 state.status === 'waiting' ? <window.Icon name="user" className="animate-bounce" size={22} /> :
                                 <span className="text-xs font-bold">{step.id}</span>}
                            </div>
                            
                            <div className={`spatial-card ${isFocused ? 'ring-2 ring-slate-900 ring-offset-2' : ''}`}>
                                <div className="flex flex-col">
                                    <div className="card-title text-base font-semibold flex items-center gap-2">
                                        {step.name}
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">{step.desc}</div>
                                </div>
                                
                                <div className="flex items-center gap-3">
                                    <window.ResultCapsule result={state.result} />
                                    
                                    {runMode === 'human' && (
                                        <button 
                                            onClick={(e) => { e.stopPropagation(); runTask(step.id); }}
                                            disabled={state.status === 'running' || isGlobalRunning}
                                            className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all ${state.status === 'running' ? 'bg-slate-50' : 'hover:bg-slate-100 hover:border-slate-300'}`}
                                        >
                                            <window.Icon name="play" size={14} className={state.status === 'running' ? "text-slate-300" : "text-slate-600"} />
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })}
            
            <div className={`node-wrapper ${Object.values(stepStates).every(s => s.status === 'completed') ? 'completed' : ''}`}>
                <div className="node-row">
                    <div className="icon-circle" style={{borderStyle: 'dashed'}}>
                        <window.Icon name="flag" size={18} />
                    </div>
                    <div className="spatial-card" style={{border: 'none', background: 'transparent', boxShadow: 'none'}}>
                        <span className="text-slate-400 text-sm font-bold tracking-widest">END</span>
                    </div>
                </div>
            </div>
        </div>
    );
};