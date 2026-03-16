document.addEventListener('DOMContentLoaded', () => {
    const csvInput = document.getElementById('csvInput');
    const personaInput = document.getElementById('persona');
    const startBtn = document.getElementById('startBtn');
    const resultsGrid = document.getElementById('resultsGrid');
    const globalStatusPanel = document.getElementById('globalStatusPanel');
    const activeThreads = document.getElementById('activeThreads');

    // Modal elements
    const detailsModal = document.getElementById('detailsModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const modalTitle = document.getElementById('modalTitle');
    const modalResearch = document.getElementById('modalResearch');
    const modalSubject = document.getElementById('modalSubject');
    const modalEmailContent = document.getElementById('modalEmailContent');
    const modalSources = document.getElementById('modalSources');

    // State
    let activeCompanyCards = {}; // Map of company name to DOM elements

    startBtn.addEventListener('click', startPipeline);

    async function startPipeline() {
        const csvData = csvInput.value.trim();
        const persona = personaInput.value;

        if (!csvData) return alert("Please enter target companies.");

        // Reset UI
        resultsGrid.innerHTML = '';
        activeCompanyCards = {};
        globalStatusPanel.classList.remove('hidden');
        startBtn.disabled = true;
        startBtn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Processing...
        `;

        try {
            // Initiate the SSE sequence via POST using fetch, but we need
            // to fetch streams differently. We'll use the Fetch API with streaming response.
            const response = await fetch('/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ csv_data: csvData, persona: persona })
            });

            if (!response.ok) {
                throw new Error("Failed to start stream");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            let buffer = "";
            let streamDone = false;
            
            // Loop over stream
            while (!streamDone) {
                const { done, value } = await reader.read();
                if (done) {
                    streamDone = true;
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                let lines = buffer.split('\n');
                // Keep the last partial line in the buffer
                buffer = lines.pop();

                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        const payloadStr = line.replace('data: ', '').trim();
                        if (payloadStr) {
                            try {
                                const event = JSON.parse(payloadStr);
                                handleEvent(event);
                            } catch (e) {
                                console.error("Error parsing SSE data:", e);
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Pipeline execution error:", error);
            globalStatusPanel.innerHTML = `<span class="text-red-400">Error connecting to matrix.</span>`;
        } finally {
            startBtn.disabled = false;
            startBtn.innerHTML = `
                <span>Execute Pipeline</span>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            `;
            globalStatusPanel.classList.add('hidden');
        }
    }

    function handleEvent(event) {
        if (event.type === "done") {
            // Stream complete
            return;
        }

        const compName = event.company;
        
        // Ensure card exists
        if (!activeCompanyCards[compName]) {
            createCard(compName);
        }
        
        const card = activeCompanyCards[compName];

        if (event.type === "status") {
            // Update terminal text
            updateTerminal(card.terminal, event.message);
            updateGlobalCounter();
        } 
        else if (event.type === "complete") {
            const result = event.data;
            if (result.status === "error") {
                finishCardError(card, result.message);
            } else {
                finishCardSuccess(card, compName, result);
            }
            updateGlobalCounter();
        }
        else if (event.type === "error") {
            finishCardError(card, event.message);
            updateGlobalCounter();
        }
    }

    function createCard(companyName) {
        const col = document.createElement('div');
        col.className = "glass-panel p-5 rounded-xl border border-glassBorder backdrop-blur-md h-64 flex flex-col relative overflow-hidden card-hover group";
        
        // Build inner HTML
        col.innerHTML = `
            <div class="flex justify-between items-start mb-4 relative z-10">
                <h3 class="font-display font-semibold text-lg text-white truncate max-w-[80%]">${companyName}</h3>
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100/10 text-cloudBlue status-badge border border-blue-500/20">
                    <svg class="animate-spin -ml-1 mr-1.5 h-3 w-3 text-cloudBlue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg> Active
                </span>
            </div>
            
            <div class="flex-grow bg-slate-900/80 rounded-lg p-3 custom-scrollbar overflow-y-auto font-mono text-[11px] text-green-400 border border-slate-800 shadow-inner terminal-container relative z-10">
                <div class="terminal-text leading-relaxed opacity-80"></div>
                <span class="animate-blink inline-block w-1.5 h-3 bg-green-400 ml-1 translate-y-0.5"></span>
            </div>
            
            <div class="mt-4 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity absolute bottom-5 right-5 z-20">
                <button class="bg-slate-700/80 hover:bg-cloudBlue text-white text-xs px-4 py-1.5 rounded-full transition-colors hidden details-btn font-medium shadow-lg backdrop-blur-sm border border-slate-600">
                    View Matrix
                </button>
            </div>
            
            <!-- Bg glow -->
            <div class="absolute inset-0 bg-gradient-to-br from-cloudBlue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-0"></div>
        `;
        
        resultsGrid.appendChild(col);
        
        activeCompanyCards[companyName] = {
            element: col,
            terminal: col.querySelector('.terminal-text'),
            statusBadge: col.querySelector('.status-badge'),
            detailsBtn: col.querySelector('.details-btn')
        };
    }

    function updateTerminal(terminalEl, text) {
        terminalEl.innerHTML += `<div>> ${text}</div>`;
        terminalEl.parentElement.scrollTop = terminalEl.parentElement.scrollHeight;
    }

    function finishCardSuccess(card, companyName, resultData) {
        card.statusBadge.className = "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100/10 text-cloudGreen status-badge border border-green-500/30";
        card.statusBadge.innerHTML = `<svg class="mr-1.5 h-3 w-3 text-cloudGreen" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Intel Built`;
        
        card.terminal.innerHTML += `<div class="text-white mt-2">Payload secured. Email drafted. Cross-sell mapped.</div>`;
        card.element.classList.add('border-green-500/30', 'shadow-[0_0_15px_rgba(52,168,83,0.15)]');
        
        card.detailsBtn.classList.remove('hidden');
        card.detailsBtn.onclick = () => openModal(companyName, resultData);
    }
    
    function finishCardError(card, errorMsg) {
        card.statusBadge.className = "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100/10 text-cloudRed status-badge border border-red-500/30";
        card.statusBadge.innerHTML = `Failed`;
        
        updateTerminal(card.terminal, `<span class="text-red-400">ERROR: ${errorMsg}</span>`);
        card.element.classList.add('border-red-500/30');
    }

    function updateGlobalCounter() {
        const total = Object.keys(activeCompanyCards).length;
        const complete = Object.values(activeCompanyCards).filter(c => 
            c.statusBadge.innerText.includes('Intel Built') || c.statusBadge.innerText.includes('Failed')
        ).length;
        
        activeThreads.innerText = `Synchronizing vectors: ${complete} / ${total}`;
    }

    // Modal Handling
    function openModal(companyName, data) {
        modalTitle.innerText = `${companyName} | Strategic Matrix`;
        
        // Parse the raw Pydantic JSONs wrapped via ADK payload
        let research = data.research || {};
        let emailObj = data.email || {};
        
        // Build Research List
        modalResearch.innerHTML = '';
        if (research.hack) {
            Object.entries(research.hack).forEach(([key, rec]) => {
                modalResearch.innerHTML += `
                    <div class="mb-4 bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
                        <div class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">${key.replace('_', ' ')}</div>
                        <div class="font-semibold text-white text-sm mb-1">${rec.solution} for ${rec.name} <span class="text-xs text-slate-400 font-normal">(${rec.persona})</span></div>
                        <div class="text-slate-300 italic text-xs leading-relaxed border-l-2 border-cloudBlue/50 pl-2">"${rec.hook}"</div>
                    </div>
                `;
            });
        }
        
        // Build Email
        modalSubject.innerText = emailObj.subject || "No Subject";
        modalEmailContent.innerHTML = emailObj.outreach_body || "Failed to generate body.";
        
        // Build Sources
        modalSources.innerHTML = '';
        if (emailObj.sources && emailObj.sources.length > 0) {
            emailObj.sources.forEach(src => {
                modalSources.innerHTML += `
                    <li class="flex items-start">
                        <svg class="h-4 w-4 text-cloudBlue mt-0.5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                        <a href="${src.url}" target="_blank" class="hover:text-white transition-colors text-slate-300 underline underline-offset-2 decoration-slate-700">${src.title}</a>
                    </li>
                `;
            });
        }
        
        // Show Modal
        detailsModal.classList.remove('hidden');
        // Trigger small delay for animation
        setTimeout(() => {
            detailsModal.classList.remove('opacity-0');
            detailsModal.querySelector('.relative').classList.remove('scale-95', 'translate-y-4');
        }, 10);
        document.body.style.overflow = 'hidden'; // prevent bg scroll
    }

    function closeModal() {
        detailsModal.classList.add('opacity-0');
        detailsModal.querySelector('.relative').classList.add('scale-95', 'translate-y-4');
        setTimeout(() => {
            detailsModal.classList.add('hidden');
            document.body.style.overflow = '';
        }, 300);
    }

    closeModalBtn.addEventListener('click', closeModal);
    detailsModal.querySelector('.modal-overlay').addEventListener('click', closeModal);
    
    // Quick copy to clipboard
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const targetId = this.getAttribute('data-clipboard-target');
            const target = document.querySelector(targetId);
            navigator.clipboard.writeText(target.innerText).then(() => {
                const originalHtml = this.innerHTML;
                this.innerHTML = `<svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
                setTimeout(() => { this.innerHTML = originalHtml; }, 2000);
            });
        });
    });
});
