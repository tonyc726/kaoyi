(function () {
  var canvas = document.getElementById("binary-field");
  if (!canvas || !canvas.getContext) {
    return;
  }

  var ctx = canvas.getContext("2d");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var particles = [];
  var raf = 0;
  var last = 0;

  function size() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var width = window.innerWidth;
    var height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { width: width, height: height };
  }

  function seed(width, height) {
    var count = Math.max(16, Math.min(48, Math.round((width * height) / 28000)));
    particles = [];
    var i;
    for (i = 0; i < count; i += 1) {
      particles.push({
        ch: Math.random() < 0.5 ? "0" : "1",
        x: Math.random() * width,
        y: Math.random() * height,
        opacity: 0.04 + Math.random() * 0.1,
        size: 11 + Math.random() * 5,
        vx: (Math.random() - 0.5) * 4,
        vy: 4 + Math.random() * 8,
      });
    }
  }

  function draw(width, height, dt) {
    var i;
    var particle;
    ctx.clearRect(0, 0, width, height);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (i = 0; i < particles.length; i += 1) {
      particle = particles[i];
      if (dt) {
        particle.x += particle.vx * dt;
        particle.y += particle.vy * dt;
        if (particle.y > height + 20) {
          particle.y = -20;
          particle.x = Math.random() * width;
        }
        if (particle.x < -20) {
          particle.x = width + 20;
        }
        if (particle.x > width + 20) {
          particle.x = -20;
        }
      }
      ctx.font = "500 " + particle.size + "px 'Geist Mono', ui-monospace, monospace";
      ctx.fillStyle = "rgba(255,255,255," + particle.opacity + ")";
      ctx.fillText(particle.ch, particle.x, particle.y);
    }
  }

  function frame(ts) {
    var dt = last ? Math.min(0.05, (ts - last) / 1000) : 0;
    last = ts;
    draw(window.innerWidth, window.innerHeight, dt);
    raf = window.requestAnimationFrame(frame);
  }

  function start() {
    var dim = size();
    seed(dim.width, dim.height);
    window.cancelAnimationFrame(raf);
    last = 0;
    draw(dim.width, dim.height, 0);
    if (reduce.matches) {
      return;
    }
    raf = window.requestAnimationFrame(frame);
  }

  window.addEventListener("resize", start);
  if (typeof reduce.addEventListener === "function") {
    reduce.addEventListener("change", start);
  } else if (typeof reduce.addListener === "function") {
    reduce.addListener(start);
  }
  start();
})();
