"use client";

import { useEffect, useRef } from 'react';
import { Terminal, Info, AlertTriangle, Activity } from 'lucide-react';

interface FeedItem {
    time: string;
    type: 'Observation' | 'Task' | 'Manual Override' | 'Event';
    summary: string;
}

export const CognitiveFeed = ({ feed }: { feed: FeedItem[] }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [feed]);

    return (
        <div className="glass-card h-[calc(100vh-18rem)] flex flex-col p-0 overflow-hidden border-primary/10">
            <div className="p-4 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-primary" />
                    <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-primary">Neural Activity Log</span>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5 font-mono text-[9px] text-muted-foreground">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                        SYNCED
                    </div>
                </div>
            </div>
            
            <div 
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 font-mono scrollbar-thin scrollbar-thumb-white/10"
            >
                {feed.map((item, idx) => (
                    <div key={idx} className="flex gap-4 group animate-in slide-in-from-left duration-300">
                        <div className="flex flex-col items-center gap-2">
                            <span className="text-[9px] text-muted-foreground opacity-50">{item.time}</span>
                            <div className={`w-0.5 flex-1 bg-gradient-to-b ${
                                item.type === 'Manual Override' ? 'from-amber-500/20 to-transparent' : 
                                item.type === 'Task' ? 'from-primary/20 to-transparent' : 
                                'from-white/10 to-transparent'
                            }`} />
                        </div>
                        <div className="flex-1 pb-2">
                            <div className="flex items-center gap-2 mb-1">
                                {item.type === 'Manual Override' && <AlertTriangle className="w-3 h-3 text-amber-500" />}
                                {item.type === 'Task' && <Activity className="w-3 h-3 text-primary" />}
                                {item.type === 'Observation' && <Info className="w-3 h-3 text-blue-400" />}
                                <span className={`text-[9px] uppercase font-black tracking-widest ${
                                    item.type === 'Manual Override' ? 'text-amber-500' : 
                                    item.type === 'Task' ? 'text-primary' : 
                                    'text-blue-400'
                                }`}>
                                    {item.type}
                                </span>
                            </div>
                            <p className="text-xs text-white/80 leading-relaxed border-l-2 border-transparent group-hover:border-primary/30 pl-2 transition-all">
                                {item.summary}
                            </p>
                        </div>
                    </div>
                ))}
                {feed.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center opacity-30 gap-4">
                        <Loader2 className="w-8 h-8 animate-spin" />
                        <p className="text-[10px] uppercase tracking-widest">Awaiting Neural Stream...</p>
                    </div>
                )}
            </div>
            
            <div className="p-3 bg-black/40 border-t border-white/5">
                <div className="flex items-center gap-2 text-[8px] text-muted-foreground uppercase tracking-widest">
                    <span className="w-1 h-1 rounded-full bg-primary" />
                    Protocol: JSON_TELEMETRY_v2.1
                </div>
            </div>
        </div>
    );
};

// Add Loader2 to imports
import { Loader2 } from 'lucide-react';
