import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import util from 'util';
import path from 'path';

const execPromise = util.promisify(exec);

export async function POST(request: Request) {
    try {
        const { agentName } = await request.json();

        if (!agentName) {
            return NextResponse.json({ error: 'Agent name is required' }, { status: 400 });
        }

        // We run the python script with the --trigger flag
        // Assuming the script is in the 'app/' directory of the next.js project
        const scriptPath = path.join(process.cwd(), 'app', 'agent_recycling_swarm.py');
        const venvPath = path.join(process.cwd(), '.venv', 'bin', 'python');
        
        const command = `${venvPath} ${scriptPath} --trigger "${agentName}"`;

        const { stdout, stderr } = await execPromise(command);

        if (stderr && !stderr.includes('Optimization: networkx/matplotlib not found')) {
            console.error('Trigger Script Stderr:', stderr);
            // We still return success if there's stdout output, as python might log warnings to stderr
        }

        return NextResponse.json({ success: true, message: `Triggered agent ${agentName}`, output: stdout });

    } catch (error) {
        console.error('API Error triggering agent:', error);
        return NextResponse.json({ error: 'Failed to trigger agent' }, { status: 500 });
    }
}
