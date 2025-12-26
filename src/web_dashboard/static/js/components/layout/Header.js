// src/web_dashboard/static/js/components/layout/Header.js

window.Header = ({ runMode, setRunMode, isGlobalRunning, runTask }) => {
    return (
        <div className="flex justify-between items-center mb-8 pb-6 border-b border-slate-200">
            <div>
                <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-white shadow-lg ${runMode === 'auto' ? 'bg-indigo-600' : 'bg-slate-900'}`}>
                        <window.Icon name="aperture" size={20} />
                    </div>
                    值班自动化系统 <span className="text-slate-300 font-light">|</span> <span className="text-slate-500 font-medium text-lg">Pipeline Console</span>
                </h1>
            </div>

            <div className="flex items-center gap-6">
                <div className="bg-slate-100 p-1 rounded-lg flex font-bold text-sm">
                    <button 
                        onClick={() => !isGlobalRunning && setRunMode('human')}
                        className={`px-4 py-2 rounded-md flex items-center gap-2 transition-all ${runMode === 'human' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        disabled={isGlobalRunning}
                    >
                        <window.Icon name="wrench" size={16} /> 交互模式
                    </button>
                    <button 
                        onClick={() => !isGlobalRunning && setRunMode('auto')}
                        className={`px-4 py-2 rounded-md flex items-center gap-2 transition-all ${runMode === 'auto' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200' : 'text-slate-500 hover:text-slate-700'}`}
                        disabled={isGlobalRunning}
                    >
                        <window.Icon name="zap" size={16} /> 全自动托管
                    </button>
                </div>

                {runMode === 'auto' && (
                    <button 
                        onClick={() => runTask(null)}
                        disabled={isGlobalRunning}
                        className={`
                            px-6 py-2.5 rounded-lg font-bold text-sm text-white flex items-center gap-2 shadow-xl shadow-indigo-200 transition-transform active:scale-95
                            ${isGlobalRunning ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 hover:-translate-y-0.5'}
                        `}
                    >
                        {isGlobalRunning ? <window.Icon name="loader-2" className="animate-spin" /> : <window.Icon name="play" fill="currentColor" />}
                        {isGlobalRunning ? 'Pipeline Running...' : 'Start Pipeline'}
                    </button>
                )}
            </div>
        </div>
    );
};