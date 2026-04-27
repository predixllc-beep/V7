import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import { EventEmitter } from 'events';

// Global Event Bus for Node backend
export const eventBus = new EventEmitter();

// --- Agent Protocol & Discovery ---
interface AgentConfig {
  id: string;
  name: string;
  source: string;
  role: string;
  model: string;
  prompt: string;
  enabled: boolean;
  risk_level: string;
  confidence_threshold: number;
}

class AgentRegistry {
  private agents: Record<string, AgentConfig> = {};
  constructor() { this.bootstrapCore(); }
  private bootstrapCore() {
    const cores: AgentConfig[] = [
      { id: 'openclaw', name: 'OpenClaw', source: 'core', role: 'executor', model: 'claude-haiku', prompt: 'Routing', enabled: true, risk_level: 'medium', confidence_threshold: 70 },
      { id: 'mirofish', name: 'Mirofish', source: 'core', role: 'signal', model: 'claude-sonnet', prompt: 'Signals', enabled: true, risk_level: 'medium', confidence_threshold: 70 },
    ];
    cores.forEach(a => this.agents[a.id] = a);
  }
  public register(agent: AgentConfig) { this.agents[agent.id] = agent; }
  public getAll() { return Object.values(this.agents); }
}

const registry = new AgentRegistry();

// Event listeners for decoupling logic
eventBus.on("signal.created", async (payload: any) => {
  // Pass to Risk Gate or directly stream to UI
  eventBus.emit("system.stream", { type: 'signal', data: payload });
});

eventBus.on("order.placed", async (payload: any) => {
  console.log(`[EventBus] Order placed:`, payload);
  eventBus.emit("system.stream", { type: 'order', data: payload });
});

async function startServer() {
  const app = express();
  const PORT = 3000;
  app.use(express.json());

  app.get('/api/agents', (req, res) => res.json(registry.getAll()));

  // Async non-blocking endpoints
  app.post('/api/hummingbot/order', async (req, res) => {
    try {
      const { tokenId, price, size, side } = req.body;
      const order = { status: 'CONFIRMED', txHash: `0x${Math.random().toString(16).slice(2)}`, tokenId, price, size, side };
      
      // Publish event asynchronously instead of awaiting heavy logic here
      eventBus.emit("order.placed", order);
      
      res.json(order);
    } catch(e: any) {
      res.status(503).json({ error: e.message });
    }
  });

  // Server-Sent Events (SSE) Bridge
  app.get('/api/stream', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    res.write(`data: ${JSON.stringify({ type: 'handshake', message: 'SSE Established' })}\n\n`);

    const onSystemStream = (payload: any) => {
      res.write(`data: ${JSON.stringify(payload)}\n\n`);
    };
    
    eventBus.on("system.stream", onSystemStream);

    req.on('close', () => {
      eventBus.off("system.stream", onSystemStream);
    });
  });

  // Simulator loop to continually feed the bus
  setInterval(() => {
    eventBus.emit("signal.created", {
      source: 'mirofish',
      confidence: Math.floor(Math.random() * 30) + 70,
      timestamp: new Date().toISOString(),
      direction: Math.random() > 0.5 ? 'LONG' : 'SHORT'
    });
  }, 5000);

  // Assign Model
  app.post('/api/agents/assign_model', async (req, res) => {
    try {
      const { agentId, modelId } = req.body;
      console.log(`[EventBus] Assigning model ${modelId} to agent ${agentId}`);
      eventBus.emit("admin.command", { 
        command: 'ASSIGN_MODEL', 
        agentId, 
        modelId 
      });
      res.json({ success: true, agentId, modelId });
    } catch(e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  // Chat interface
  app.post('/api/chat', async (req, res) => {
    const { messages } = req.body;
    const cmd = messages[messages.length - 1]?.content || "";
    
    // Simulate orchestration
    eventBus.emit("admin.command", { cmd });
    
    res.json({ content: [{ text: `[OpenClaw Executor] Acknowledged: ${cmd}` }] });
  });

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: 'spa' });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => res.sendFile(path.join(distPath, 'index.html')));
  }

  app.listen(PORT, '0.0.0.0', () => console.log(`POULS Server running on http://localhost:${PORT}`));
}
startServer();
