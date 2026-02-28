"use client";

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import { 
    ChevronLeft, Brain, Target, Award, Activity, 
    Calendar, Database, Cpu, Shield, Zap, TrendingUp,
    MessageSquare, AlertCircle
} from 'lucide-react';
import { 
    Radar, RadarChart, PolarGrid, PolarAngleAxis, 
    PolarRadiusAxis, ResponsiveContainer, 
    BarChart, Bar, XAxis, YAxis, Tooltip
} from 'recharts';

export default function AgentDetail() {
    const { name } = useParams();
    const router = useRouter();
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch('/stats.json', { cache: 'no-store' });
                const json = await res.json();
                const agent = json.agents.find((a: any) => a.name === name);
                setData({ 
                    agent, 
                    history: json.feed.filter((item: any) => item.summary.includes(name)),
                    timestamp: json.timestamp
                });
                setLoading(false);
            } catch (e) {
                console.error(e);
            }
        };
        fetchStats();
        const interval = setInterval(fetchStats, 5000);
        return () => clearInterval(interval);
    }, [name]);

    if (loading || !data?.agent) {
        return (
            <div className="flex h-screen items-center justify-center bg-black text-primary font-mono animate-pulse">
                Decrypting Agent Neural Profile...
            </div>
        );
    }

    const { agent, history } = data;

    // Simulation of radar data for fitness breakdown
    const radarData = [
        { subject: 'Success Rate', A: agent.task_success_rate, fullMark: 100 },
        { subject: 'Knowledge', A: Math.min(agent.knowledge_contrib * 5, 100), fullMark: 100 },
        { subject: 'Reliability', A: 85, fullMark: 100 },
        { subject: 'Independence', A: 70, fullMark: 100 },
        { subject: 'Synergy', A: agent.fitness, fullMark: 100 },
    ];

    return (
        <>
                <button 
                    onClick={() => router.back()}
                    className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-8 group"
                >
                    <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
                    <span className="text-[10px] uppercase font-bold tracking-widest">Back to Swarm</span>
                </button>

                <div className="grid grid-cols-12 gap-8">
                    {/* Left Column: Profile Card */}
                    <div className="col-span-12 lg:col-span-4 space-y-8">
                        <section className="glass-card border-primary/20 bg-primary/[0.02] flex flex-col items-center text-center p-8">
                            <div className="relative mb-6">
                                <div className="w-32 h-32 rounded-3xl bg-primary/20 flex items-center justify-center border border-primary/40 shadow-[0_0_50px_rgba(var(--primary),0.2)]">
                                    <Brain className="w-16 h-16 text-primary" />
                                </div>
                                <div className="absolute -bottom-2 -right-2 px-3 py-1 rounded-full bg-green-500 text-black text-[10px] font-black uppercase tracking-tighter">
                                    Operational
                                </div>
                            </div>
                            
                            <h1 className="text-3xl font-black premium-gradient-text uppercase tracking-tighter">{agent.name}</h1>
                            <p className="text-sm text-muted-foreground uppercase tracking-[0.3em] font-medium mt-1">{agent.role}</p>
                            
                            <div className="flex gap-2 mt-6">
                                <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] uppercase font-bold text-muted-foreground">{agent.culture}</span>
                                <span className="px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-[10px] uppercase font-bold text-blue-400">{agent.model}</span>
                            </div>

                            <div className="w-full mt-10 grid grid-cols-2 gap-4">
                                <div className="p-4 rounded-2xl bg-black/40 border border-white/5">
                                    <p className="text-[8px] text-muted-foreground uppercase tracking-widest mb-1">Global Fitness</p>
                                    <p className="text-2xl font-black text-primary">{agent.fitness}%</p>
                                </div>
                                <div className="p-4 rounded-2xl bg-black/40 border border-white/5">
                                    <p className="text-[8px] text-muted-foreground uppercase tracking-widest mb-1">Success Rate</p>
                                    <p className="text-2xl font-black text-white">{agent.task_success_rate}%</p>
                                </div>
                            </div>
                        </section>

                        <section className="glass-card">
                            <h3 className="text-xs font-bold mb-6 uppercase tracking-widest text-primary flex items-center gap-2">
                                <Shield className="w-4 h-4" />
                                Capability Matrix
                            </h3>
                            <div className="h-[250px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                        <PolarGrid stroke="#222" />
                                        <PolarAngleAxis dataKey="subject" stroke="#666" fontSize={10} />
                                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                                        <Radar
                                            name={agent.name}
                                            dataKey="A"
                                            stroke="#3b82f6"
                                            fill="#3b82f6"
                                            fillOpacity={0.6}
                                        />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                        </section>
                    </div>

                    {/* Right Column: Execution History & Details */}
                    <div className="col-span-12 lg:col-span-8 space-y-8">
                        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
                           <div className="glass-card space-y-4">
                               <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                                   <Target className="w-4 h-4" />
                                   Core Parameters
                               </h3>
                               <div className="space-y-3">
                                   {[
                                       { label: 'Neural Personality', val: 'Specialist' },
                                       { label: 'Latency Node', val: 'LOCAL_EDGE' },
                                       { label: 'Contribution Weight', val: agent.knowledge_contrib },
                                       { label: 'Retirement Phase', val: 'ACTIVE_V2' }
                                   ].map((item, i) => (
                                       <div key={i} className="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                                            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">{item.label}</span>
                                            <span className="text-xs font-mono text-white/90">{item.val}</span>
                                       </div>
                                   ))}
                               </div>
                           </div>

                           <div className="glass-card space-y-4">
                               <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                                   <Zap className="w-4 h-4" />
                                   Skill Inventory
                               </h3>
                               <div className="flex flex-wrap gap-2">
                                   {['Analysis', 'Reporting', 'Verification', 'Swarm Link'].map(skill => (
                                       <span key={skill} className="px-3 py-2 rounded-lg bg-primary/5 border border-primary/20 text-[10px] uppercase font-bold text-primary">
                                           {skill}
                                       </span>
                                   ))}
                               </div>
                               <h3 className="text-xs font-bold uppercase tracking-widest text-primary flex items-center gap-2 pt-4">
                                   <Database className="w-4 h-4" />
                                   Tool Access
                               </h3>
                               <div className="flex flex-wrap gap-2">
                                   {['Terminal', 'Debugger', 'Ollama_API'].map(tool => (
                                       <span key={tool} className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-[10px] uppercase font-bold text-white/70">
                                           {tool}
                                       </span>
                                   ))}
                               </div>
                           </div>
                        </section>

                        <section className="glass-card flex flex-col h-[500px]">
                            <h3 className="text-xs font-bold mb-6 uppercase tracking-widest text-primary flex items-center gap-2">
                                <Activity className="w-4 h-4" />
                                Execution Neural History
                            </h3>
                            <div className="flex-1 overflow-y-auto space-y-4 pr-2 font-mono">
                                {history.map((item: any, i: number) => (
                                    <div key={i} className="p-4 rounded-xl bg-white/[0.02] border border-white/5 flex gap-4 hover:border-primary/20 transition-all">
                                        <span className="text-[10px] text-muted-foreground pt-1">{item.time}</span>
                                        <div className="space-y-1">
                                            <p className="text-[10px] font-black uppercase tracking-widest text-primary">{item.type}</p>
                                            <p className="text-xs text-white/80 leading-relaxed">{item.summary}</p>
                                        </div>
                                    </div>
                                ))}
                                {history.length === 0 && (
                                    <div className="flex flex-col items-center justify-center h-full opacity-30 gap-4 uppercase tracking-[0.2em] text-[10px]">
                                        <AlertCircle className="w-6 h-6" />
                                        No Direct Interactions Logged
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>
                </div>
        </>
    );
}
