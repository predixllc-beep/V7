import fs from 'fs';
import path from 'path';

function replaceInDir(dir, findRegex, replaceStr) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      replaceInDir(fullPath, findRegex, replaceStr);
    } else if (fullPath.endsWith('.py')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      const orig = content;
      content = content.replace(findRegex, replaceStr);
      if (content !== orig) {
        fs.writeFileSync(fullPath, content);
        console.log(`Updated ${fullPath}`);
      }
    }
  }
}

const dirs = ['./agents', './core', './execution', './hummingbot_bridge', './observability', './control_plane', './ai_memory'];
for (const d of dirs) {
  if (fs.existsSync(d)) {
    replaceInDir(d, /dataclaw_core\.events/g, 'core.events');
    replaceInDir(d, /dataclaw_core\./g, '');
  }
}
