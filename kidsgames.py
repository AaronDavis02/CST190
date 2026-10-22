import time
import json
import webbrowser
import os

THEMES = [
    {
        "name": "Crystal Caves",
        "background": "linear-gradient(135deg, #6a4cff, #b084f5)",
        "challenge": "maths",
        "reward": "Crystal Shard"
    },
    {
        "name": "Forest Friends",
        "background": "linear-gradient(135deg, #7ed957, #4caf50)",
        "challenge": "spelling",
        "reward": "Leaf Badge"
    },
    {
        "name": "Ocean Pals",
        "background": "linear-gradient(135deg, #00bbf9, #00f5d4)",
        "challenge": "problem",
        "reward": "Bubble Medal"
    },
    {
        "name": "Sky Songs",
        "background": "linear-gradient(135deg, #90e0ef, #caf0f8)",
        "challenge": "logic",
        "reward": "Feather Token"
    },
    {
        "name": "Library Lane",
        "background": "linear-gradient(135deg, #ffd166, #ff9f1c)",
        "challenge": "creativity",
        "reward": "Bookmark Ribbon"
    }
]

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Adventure Engine</title>
<meta http-equiv="refresh" content="30">

<style>
body {
    margin: 0;
    background: __BACKGROUND__;
    font-family: 'Comic Sans MS', sans-serif;
    color: #fff;
}
#app {
    max-width: 900px;
    margin: 20px auto;
    background: rgba(0,0,0,0.25);
    padding: 20px;
    border-radius: 24px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}
h1 {
    text-align: center;
    font-size: 36px;
}
.menu {
    text-align: center;
    margin-top: 20px;
}
.menu button {
    padding: 12px 20px;
    margin: 10px;
    border-radius: 12px;
    border: none;
    background: #fff;
    color: #333;
    font-size: 18px;
    cursor: pointer;
}
.reward {
    margin-top: 20px;
    text-align: center;
    font-size: 20px;
}
audio {
    display: none;
}
@keyframes sparkle {
    0% { transform: scale(1); box-shadow: 0 0 10px #fff; }
    50% { transform: scale(1.1); box-shadow: 0 0 20px #fff; }
    100% { transform: scale(1); box-shadow: 0 0 10px #fff; }
}
</style>
</head>

<body>
<div id="app">
    <h1>__THEME__</h1>

    <div class="menu">
        <button onclick="startChallenge()">Start __CHALLENGE__ Challenge</button>
    </div>

    <div class="reward" id="rewardBox"></div>

    <audio id="bgMusic" loop>
        <source src="https://files.catbox.moe/1zq4q9.mp3" type="audio/mpeg">
    </audio>

    <div class="menu">
        <button onclick="toggleMusic()">Play / Pause Music</button>
    </div>
</div>

<script>
const DATA = __DATA__;

function toggleMusic() {
    const m = document.getElementById("bgMusic");
    if (m.paused) m.play();
    else m.pause();
}

function startChallenge() {
    if (DATA.name === "Crystal Caves") {
        startCrystalCavesMenu();
    } else if (DATA.name === "Forest Friends") {
        startForestFriendsRandom();
    } else if (DATA.name === "Ocean Pals") {
        startOceanPalsMenu();
    } else if (DATA.name === "Sky Songs") {
        startSkySongsRandom();
    } else if (DATA.name === "Library Lane") {
        startLibraryLaneMenu();
    } else {
        document.getElementById("rewardBox").innerHTML =
            "This theme's challenge is not added yet.";
    }
}

/* ---------- Crystal Caves: menu with 3 maths puzzles ---------- */

function startCrystalCavesMenu() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Crystal Caves</h2>
        <p>Choose your puzzle:</p>
        <button onclick="crystalPuzzleA()">Puzzle A – Simple Sum</button>
        <button onclick="crystalPuzzleB()">Puzzle B – Missing Number</button>
        <button onclick="crystalPuzzleC()">Puzzle C – Crystal Equation</button>
    `;
}

function crystalPuzzleA() {
    const box = document.getElementById("rewardBox");
    const a = Math.floor(Math.random() * 5) + 1;
    const b = Math.floor(Math.random() * 5) + 1;
    const answer = a + b;

    box.innerHTML = `
        <h2>Puzzle A – Simple Sum</h2>
        <p>${a} + ${b} = ?</p>
        <input id="crystalA" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkCrystalA(${answer})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkCrystalA(correct) {
    const val = parseInt(document.getElementById("crystalA").value);
    showCrystalResult(val === correct);
}

function crystalPuzzleB() {
    const box = document.getElementById("rewardBox");
    const seq = [2, 4, 6, 8];
    const missingIndex = 2;
    const correct = seq[missingIndex];
    const displaySeq = seq.map((n, i) => i === missingIndex ? "?" : n);

    box.innerHTML = `
        <h2>Puzzle B – Missing Number</h2>
        <p>Fill in the missing number:</p>
        <h3>${displaySeq.join(" , ")}</h3>
        <input id="crystalB" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkCrystalB(${correct})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkCrystalB(correct) {
    const val = parseInt(document.getElementById("crystalB").value);
    showCrystalResult(val === correct);
}

function crystalPuzzleC() {
    const box = document.getElementById("rewardBox");
    const x = Math.floor(Math.random() * 5) + 1;
    const answer = x + 3;

    box.innerHTML = `
        <h2>Puzzle C – Crystal Equation</h2>
        <p>If x = ${x}, what is x + 3?</p>
        <input id="crystalC" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkCrystalC(${answer})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkCrystalC(correct) {
    const val = parseInt(document.getElementById("crystalC").value);
    showCrystalResult(val === correct);
}

function showCrystalResult(success) {
    const box = document.getElementById("rewardBox");
    if (success) {
        box.innerHTML = `
            <h2>Correct!</h2>
            <p>You earned a <strong>Crystal Shard</strong>!</p>
            <div style="
                margin-top:20px;
                width:80px;
                height:80px;
                background: radial-gradient(circle, #b084f5, #6a4cff);
                border-radius:20px;
                animation: sparkle 1s infinite;
            "></div>
        `;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Try again!</p>`;
    }
}

/* ---------- Forest Friends: random spelling puzzle ---------- */

function startForestFriendsRandom() {
    const puzzles = [forestPuzzleA, forestPuzzleB, forestPuzzleC];
    const chosen = puzzles[Math.floor(Math.random() * puzzles.length)];
    chosen();
}

function forestPuzzleA() {
    const box = document.getElementById("rewardBox");
    const words = ["cat", "dog", "bird", "leaf", "tree"];
    const word = words[Math.floor(Math.random() * words.length)];
    const letters = word.split("");
    const shuffled = letters.slice().sort(() => Math.random() - 0.5);

    box.innerHTML = `
        <h2>Forest Spelling – Tap Order</h2>
        <p>Tap letters in order to spell the word:</p>
        <div id="forestTiles"></div>
        <div id="forestAnswer" style="margin-top:15px; font-size:24px;"></div>
    `;

    const tilesDiv = document.getElementById("forestTiles");
    tilesDiv.innerHTML = shuffled.map((l, i) => `
        <button onclick="forestTap('${word}', '${l}', ${i})"
            style="
                width:50px;
                height:50px;
                margin:5px;
                border-radius:16px;
                border:none;
                background:#7ed957;
                color:#fff;
                font-size:24px;
                font-weight:bold;
                box-shadow:0 4px 8px rgba(0,0,0,0.2);
            ">
            ${l.toUpperCase()}
        </button>
    `).join("");

    window.forestState = {
        target: word,
        built: "",
        used: Array(shuffled.length).fill(false)
    };
}

function forestTap(target, letter, index) {
    const state = window.forestState;
    if (!state || state.used[index]) return;

    state.used[index] = true;
    state.built += letter;

    const answerDiv = document.getElementById("forestAnswer");
    answerDiv.textContent = state.built.toUpperCase();

    if (state.built.length === state.target.length) {
        const box = document.getElementById("rewardBox");
        if (state.built === state.target) {
            box.innerHTML += `
                <p style="margin-top:10px;">Correct! You earned a <strong>Leaf Badge</strong>!</p>
                <div style="
                    margin-top:10px;
                    width:80px;
                    height:80px;
                    background: radial-gradient(circle, #7ed957, #4caf50);
                    border-radius:50%;
                    box-shadow:0 0 15px #caffbf;
                "></div>
            `;
        } else {
            box.innerHTML += `
                <p style="margin-top:10px; color:#ff595e;">That wasn't quite right.</p>
            `;
        }
    }
}

function forestPuzzleB() {
    const box = document.getElementById("rewardBox");
    const word = "log";
    const missingIndex = 1;
    const letters = word.split("");
    const display = letters.map((l, i) => i === missingIndex ? "_" : l);

    box.innerHTML = `
        <h2>Forest Spelling – Missing Letter</h2>
        <p>Fill in the missing letter:</p>
        <h3>${display.join(" ")}</h3>
        <input id="forestB" type="text" maxlength="1"
            style="font-size:20px; padding:6px; width:40px;">
        <button onclick="checkForestB('${letters[missingIndex]}')"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkForestB(correct) {
    const val = document.getElementById("forestB").value.toLowerCase();
    const box = document.getElementById("rewardBox");
    if (val === correct) {
        box.innerHTML += `
            <p>Nice! Leaf Badge earned!</p>
        `;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Try again.</p>`;
    }
}

function forestPuzzleC() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Forest Spelling – Count Letters</h2>
        <p>How many letters are in the word "forest"?</p>
        <input id="forestC" type="number" style="font-size:20px; padding:6px; width:60px;">
        <button onclick="checkForestC(6)"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkForestC(correct) {
    const val = parseInt(document.getElementById("forestC").value);
    const box = document.getElementById("rewardBox");
    if (val === correct) {
        box.innerHTML += `<p>Correct! Leaf Badge!</p>`;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Not quite.</p>`;
    }
}

/* ---------- Ocean Pals: menu with 3 pattern puzzles ---------- */

function startOceanPalsMenu() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Ocean Pals</h2>
        <p>Choose your puzzle:</p>
        <button onclick="oceanPuzzleA()">Puzzle A – Number Pattern</button>
        <button onclick="oceanPuzzleB()">Puzzle B – Even Numbers</button>
        <button onclick="oceanPuzzleC()">Puzzle C – Skip Counting</button>
    `;
}

function oceanPuzzleA() {
    const box = document.getElementById("rewardBox");
    const seq = [1, 2, 3, 4];
    const missingIndex = 2;
    const correct = seq[missingIndex];
    const display = seq.map((n, i) => i === missingIndex ? "?" : n);

    box.innerHTML = `
        <h2>Number Pattern</h2>
        <p>Fill in the missing number:</p>
        <h3>${display.join(" , ")}</h3>
        <input id="oceanA" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkOceanA(${correct})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkOceanA(correct) {
    const val = parseInt(document.getElementById("oceanA").value);
    showOceanResult(val === correct);
}

function oceanPuzzleB() {
    const box = document.getElementById("rewardBox");
    const seq = [2, 4, 6, 8];
    const missingIndex = 1;
    const correct = seq[missingIndex];
    const display = seq.map((n, i) => i === missingIndex ? "?" : n);

    box.innerHTML = `
        <h2>Even Numbers</h2>
        <p>Fill in the missing even number:</p>
        <h3>${display.join(" , ")}</h3>
        <input id="oceanB" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkOceanB(${correct})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkOceanB(correct) {
    const val = parseInt(document.getElementById("oceanB").value);
    showOceanResult(val === correct);
}

function oceanPuzzleC() {
    const box = document.getElementById("rewardBox");
    const seq = [5, 10, 15, 20];
    const missingIndex = 3;
    const correct = seq[missingIndex];
    const display = seq.map((n, i) => i === missingIndex ? "?" : n);

    box.innerHTML = `
        <h2>Skip Counting</h2>
        <p>Fill in the missing number:</p>
        <h3>${display.join(" , ")}</h3>
        <input id="oceanC" type="number" style="font-size:20px; padding:6px; width:80px;">
        <button onclick="checkOceanC(${correct})"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkOceanC(correct) {
    const val = parseInt(document.getElementById("oceanC").value);
    showOceanResult(val === correct);
}

function showOceanResult(success) {
    const box = document.getElementById("rewardBox");
    if (success) {
        box.innerHTML = `
            <h2>Wave‑tastic!</h2>
            <p>You earned a <strong>Bubble Medal</strong>!</p>
            <div style="
                margin-top:20px;
                width:80px;
                height:80px;
                background: radial-gradient(circle, #00f5d4, #00bbf9);
                border-radius:50%;
                box-shadow:0 0 20px #caf0f8;
            "></div>
        `;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Look at the pattern and try again!</p>`;
    }
}

/* ---------- Sky Songs: random logic puzzle ---------- */

function startSkySongsRandom() {
    const puzzles = [skyPuzzleA, skyPuzzleB, skyPuzzleC];
    const chosen = puzzles[Math.floor(Math.random() * puzzles.length)];
    chosen();
}

function skyPuzzleA() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Sky Logic – True/False</h2>
        <p>All birds can fly. Is this always true?</p>
        <button onclick="checkSkyA(false)">True</button>
        <button onclick="checkSkyA(true)">False</button>
    `;
}
function checkSkyA(correctChoice) {
    const box = document.getElementById("rewardBox");
    if (correctChoice) {
        box.innerHTML += `<p>Right! Some birds cannot fly. Feather Token!</p>`;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Not quite.</p>`;
    }
}

function skyPuzzleB() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Sky Logic – Order</h2>
        <p>Put these in order from lowest to highest:</p>
        <p>Cloud, Bird, Airplane</p>
        <p>(Just think it through – this one is reflective!)</p>
    `;
}

function skyPuzzleC() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Sky Logic – Count</h2>
        <p>If there are 3 birds and 2 more join, how many birds are there?</p>
        <input id="skyC" type="number" style="font-size:20px; padding:6px; width:60px;">
        <button onclick="checkSkyC(5)"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkSkyC(correct) {
    const val = parseInt(document.getElementById("skyC").value);
    const box = document.getElementById("rewardBox");
    if (val === correct) {
        box.innerHTML += `<p>Nice thinking! Feather Token!</p>`;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Try again.</p>`;
    }
}

/* ---------- Library Lane: menu with 3 creativity tasks ---------- */

function startLibraryLaneMenu() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Library Lane</h2>
        <p>Choose your creativity task:</p>
        <button onclick="libraryPuzzleA()">Puzzle A – Story Starter</button>
        <button onclick="libraryPuzzleB()">Puzzle B – Word Builder</button>
        <button onclick="libraryPuzzleC()">Puzzle C – Book Count</button>
    `;
}

function libraryPuzzleA() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Story Starter</h2>
        <p>Finish this sentence in your head:</p>
        <p>"Once upon a time, in a tiny library..."</p>
        <p>Think of what happens next!</p>
    `;
}

function libraryPuzzleB() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Word Builder</h2>
        <p>How many words can you make from the letters in "BOOK"?</p>
        <p>Say them out loud!</p>
    `;
}

function libraryPuzzleC() {
    const box = document.getElementById("rewardBox");
    box.innerHTML = `
        <h2>Book Count</h2>
        <p>If you have 4 books and get 3 more, how many books do you have?</p>
        <input id="libC" type="number" style="font-size:20px; padding:6px; width:60px;">
        <button onclick="checkLibraryC(7)"
            style="padding:10px 20px; margin-left:10px; font-size:18px;">
            Submit
        </button>
    `;
}
function checkLibraryC(correct) {
    const val = parseInt(document.getElementById("libC").value);
    const box = document.getElementById("rewardBox");
    if (val === correct) {
        box.innerHTML += `<p>Great! Bookmark Ribbon!</p>`;
    } else {
        box.innerHTML += `<p style="color:#ff595e;">Try again.</p>`;
    }
}
</script>

</body>
</html>
"""

OUTPUT_FILE = "adventure_engine.html"

def write_html(theme):
    html = HTML_TEMPLATE.replace("__THEME__", theme["name"])
    html = html.replace("__BACKGROUND__", theme["background"])
    html = html.replace("__CHALLENGE__", theme["challenge"])
    html = html.replace("__DATA__", json.dumps(theme))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    webbrowser.open("file://" + os.path.abspath(OUTPUT_FILE))

    index = 0
    while True:
        write_html(THEMES[index])
        index = (index + 1) % len(THEMES)
        time.sleep(30)

if __name__ == "__main__":
    main()

