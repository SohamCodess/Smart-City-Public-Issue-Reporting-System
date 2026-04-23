window.onload = function () {

  console.log("WINDOW LOADED");

  const citizens = document.getElementById("citizens");
  const issues   = document.getElementById("issues");
  const solved   = document.getElementById("solved");

  console.log(citizens, issues, solved);

  if (!citizens || !issues || !solved) {
    console.log("IDs not found on this page");
    return;
  }

  fetch("/live-stats")
    .then(res => res.json())
    .then(data => {
      console.log("DATA:", data);

      citizens.innerText = "👤 Citizens Registered: " + data.citizens;
      issues.innerText   = "📝 Issues Registered: " + data.issues;
      solved.innerText   = "✅ Issues Solved: " + data.solved;
    })
    .catch(err => console.error(err));
};
