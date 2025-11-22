// Client-side logic for voting UI

document.addEventListener('DOMContentLoaded', function() {
    const voteForm = document.getElementById('voteForm');
    const alertContainer = document.getElementById('alertContainer');
    const submitBtn = document.getElementById('submitBtn');
    const submitText = document.getElementById('submitText');
    const submitSpinner = document.getElementById('submitSpinner');
    const resultsContainer = document.getElementById('resultsContainer');

    // Form validation
    const nasInput = document.getElementById('nas');
    const codeInput = document.getElementById('code');

    // NAS input validation (digits only)
    nasInput.addEventListener('input', function(e) {
        this.value = this.value.replace(/[^0-9]/g, '');
        validateNAS();
    });

    // Code input validation
    codeInput.addEventListener('input', function(e) {
        this.value = this.value.replace(/[^a-zA-Z0-9]/g, '');
        validateCode();
    });

    function validateNAS() {
        const nas = nasInput.value;
        if (nas.length === 0) {
            nasInput.classList.remove('is-valid', 'is-invalid');
            return false;
        } else if (nas.length === 9 && /^[0-9]{9}$/.test(nas)) {
            nasInput.classList.remove('is-invalid');
            nasInput.classList.add('is-valid');
            return true;
        } else {
            nasInput.classList.remove('is-valid');
            nasInput.classList.add('is-invalid');
            return false;
        }
    }

    function validateCode() {
        const code = codeInput.value;
        if (code.length === 0) {
            codeInput.classList.remove('is-valid', 'is-invalid');
            return false;
        } else if (code.length === 6) {
            codeInput.classList.remove('is-invalid');
            codeInput.classList.add('is-valid');
            return true;
        } else {
            codeInput.classList.remove('is-valid');
            codeInput.classList.add('is-invalid');
            return false;
        }
    }

    // Form submission
    voteForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Validate form
        if (!validateNAS() || !validateCode()) {
            showAlert('Veuillez corriger les erreurs dans le formulaire.', 'danger');
            return;
        }

        // Disable submit button
        submitBtn.disabled = true;
        submitText.textContent = 'Envoi en cours...';
        submitSpinner.classList.remove('d-none');

        // Get form data
        const formData = new FormData(voteForm);

        try {
            const response = await fetch('/vote', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                showAlert(data.message, 'success');
                voteForm.reset();
                nasInput.classList.remove('is-valid');
                codeInput.classList.remove('is-valid');

                // Refresh results
                setTimeout(loadResults, 500);
            } else {
                showAlert(data.message, 'danger');
            }
        } catch (error) {
            showAlert('Erreur de connexion au serveur. Veuillez réessayer.', 'danger');
            console.error('Error:', error);
        } finally {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitText.textContent = 'Soumettre le Vote';
            submitSpinner.classList.add('d-none');
        }
    });

    // Show alert message
    function showAlert(message, type) {
        const alertHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                <strong>${type === 'success' ? 'Succès!' : 'Erreur!'}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        alertContainer.innerHTML = alertHTML;

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = alertContainer.querySelector('.alert');
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }

    // Load and display current results
    async function loadResults() {
        if (!resultsContainer) return;

        try {
            const response = await fetch('/api/results');
            if (!response.ok) {
                throw new Error('Failed to fetch results');
            }

            const results = await response.json();
            displayResults(results);
        } catch (error) {
            console.error('Error loading results:', error);
            resultsContainer.innerHTML = `
                <div class="alert alert-warning" role="alert">
                    Impossible de charger les résultats actuels.
                </div>
            `;
        }
    }

    // Display results in a compact format
    function displayResults(results) {
        if (!results || !Array.isArray(results) || results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="alert alert-info" role="alert">
                    Aucun résultat disponible pour le moment.
                </div>
            `;
            return;
        }

        let html = '<div class="list-group">';

        results.forEach(law => {
            const oui = law.oui_count || 0;
            const non = law.non_count || 0;
            const total = law.total_votes || 0;
            const ouiPercent = total > 0 ? ((oui / total) * 100).toFixed(1) : 0;
            const nonPercent = total > 0 ? ((non / total) * 100).toFixed(1) : 0;

            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6 class="mb-0"><strong>${law.law_id}</strong></h6>
                        <small class="text-muted">Total: ${total} votes</small>
                    </div>
                    <div class="progress mb-2" style="height: 25px;">
                        <div class="progress-bar bg-success" role="progressbar"
                             style="width: ${ouiPercent}%;"
                             aria-valuenow="${ouiPercent}"
                             aria-valuemin="0"
                             aria-valuemax="100">
                            OUI: ${oui} (${ouiPercent}%)
                        </div>
                        <div class="progress-bar bg-danger" role="progressbar"
                             style="width: ${nonPercent}%;"
                             aria-valuenow="${nonPercent}"
                             aria-valuemin="0"
                             aria-valuemax="100">
                            NON: ${non} (${nonPercent}%)
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        resultsContainer.innerHTML = html;
    }

    // Auto-refresh results every 5 seconds on voting page
    if (resultsContainer) {
        loadResults();
        setInterval(loadResults, 5000);
    }

    // Real-time input formatting
    nasInput.addEventListener('keypress', function(e) {
        if (!/[0-9]/.test(e.key) && e.key !== 'Backspace' && e.key !== 'Delete') {
            e.preventDefault();
        }
    });

    codeInput.addEventListener('keypress', function(e) {
        if (!/[a-zA-Z0-9]/.test(e.key) && e.key !== 'Backspace' && e.key !== 'Delete') {
            e.preventDefault();
        }
    });

    // Focus management
    nasInput.addEventListener('blur', validateNAS);
    codeInput.addEventListener('blur', validateCode);
});

// Utility function for refreshing results (used in results.html)
function refreshResults() {
    // This function is defined in results.html template
    console.log('Refreshing results...');
}


// ═══════════════════════════════════════════════════════════════════
// ELECTION VOTING LOGIC
// ═══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    const electionNas = document.getElementById('electionNas');
    const electionCode = document.getElementById('electionCode');
    const electionSelect = document.getElementById('electionSelect');
    const regionSelect = document.getElementById('regionSelect');
    const candidatesContainer = document.getElementById('candidatesContainer');
    const candidatesList = document.getElementById('candidatesList');
    const electionVoteForm = document.getElementById('electionVoteForm');
    const electionSubmitBtn = document.getElementById('electionSubmitBtn');
    const electionSubmitText = document.getElementById('electionSubmitText');
    const electionSubmitSpinner = document.getElementById('electionSubmitSpinner');
    const electionAlertContainer = document.getElementById('electionAlertContainer');
    const electionResultsCard = document.getElementById('electionResultsCard');
    const electionResultsContainer = document.getElementById('electionResultsContainer');
    const votingMethodContainer = document.getElementById('votingMethodContainer');
    const rankedChoiceToggle = document.getElementById('rankedChoiceToggle');
    const rankedChoiceInfo = document.getElementById('rankedChoiceInfo');
    const singleChoiceInfo = document.getElementById('singleChoiceInfo');
    const candidatesLabel = document.getElementById('candidatesLabel');

    let selectedCandidateId = null;
    let selectedElectionId = null;
    let selectedRegionId = null;
    let isRankedChoice = false;
    let rankedCandidates = [];  // Array of candidate IDs in order of preference
    let allCandidates = [];  // Store all candidates for ranking

    // Input validation for election NAS
    if (electionNas) {
        electionNas.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    }

    // Input validation for election code
    if (electionCode) {
        electionCode.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^a-zA-Z0-9]/g, '');
        });
    }

    // Load elections
    async function loadElections() {
        try {
            const response = await fetch('/api/elections');
            const elections = await response.json();

            if (elections && elections.length > 0) {
                electionSelect.innerHTML = '<option value="" selected disabled>Sélectionnez une élection...</option>';
                elections.forEach(election => {
                    const option = document.createElement('option');
                    option.value = election.id;
                    option.textContent = `${election.election_name} (${election.election_type})`;
                    electionSelect.appendChild(option);
                });
            } else {
                electionSelect.innerHTML = '<option value="" selected disabled>Aucune élection disponible</option>';
            }
        } catch (error) {
            console.error('Error loading elections:', error);
            electionSelect.innerHTML = '<option value="" selected disabled>Erreur de chargement</option>';
        }
    }

    // Load regions
    async function loadRegions() {
        try {
            const response = await fetch('/api/regions');
            const regions = await response.json();

            if (regions && regions.length > 0) {
                regionSelect.innerHTML = '<option value="" selected disabled>Sélectionnez votre région...</option>';
                regions.forEach(region => {
                    const option = document.createElement('option');
                    option.value = region.id;
                    option.textContent = region.region_name;
                    regionSelect.appendChild(option);
                });
            } else {
                regionSelect.innerHTML = '<option value="" selected disabled>Aucune région disponible</option>';
            }
        } catch (error) {
            console.error('Error loading regions:', error);
            regionSelect.innerHTML = '<option value="" selected disabled>Erreur de chargement</option>';
        }
    }

    // Toggle handler for ranked choice
    if (rankedChoiceToggle) {
        rankedChoiceToggle.addEventListener('change', function() {
            isRankedChoice = this.checked;
            if (isRankedChoice) {
                rankedChoiceInfo.style.display = 'block';
                singleChoiceInfo.style.display = 'none';
                candidatesLabel.textContent = 'Classez les candidats par ordre de préférence';
            } else {
                rankedChoiceInfo.style.display = 'none';
                singleChoiceInfo.style.display = 'block';
                candidatesLabel.textContent = 'Sélectionnez votre candidat';
            }
            // Reload candidates with new mode
            if (selectedElectionId && selectedRegionId) {
                loadCandidates();
            }
        });
    }

    // Load candidates when both election and region are selected
    async function loadCandidates() {
        if (!selectedElectionId || !selectedRegionId) {
            candidatesContainer.style.display = 'none';
            votingMethodContainer.style.display = 'none';
            electionSubmitBtn.disabled = true;
            return;
        }

        try {
            const response = await fetch(`/api/elections/${selectedElectionId}/regions/${selectedRegionId}/candidates`);
            const candidates = await response.json();
            allCandidates = candidates;

            if (candidates && candidates.length > 0) {
                votingMethodContainer.style.display = 'block';

                if (isRankedChoice) {
                    // RANKED CHOICE MODE - Display with ranking controls
                    rankedCandidates = [];
                    let html = '<div id="rankingList" class="list-group">';
                    candidates.forEach((candidate, index) => {
                        const colorStyle = candidate.party_color || '#6c757d';
                        html += `
                            <div class="list-group-item candidate-rank-item" data-candidate-id="${candidate.id}">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div class="flex-grow-1">
                                        <div class="form-check">
                                            <input class="form-check-input rank-checkbox" type="checkbox"
                                                   id="rank_${candidate.id}" value="${candidate.id}">
                                            <label class="form-check-label" for="rank_${candidate.id}">
                                                <strong>${candidate.first_name} ${candidate.last_name}</strong>
                                                <span class="badge ms-2" style="background-color: ${colorStyle};">
                                                    ${candidate.party_code}
                                                </span>
                                                <span class="text-muted">${candidate.party_name}</span>
                                            </label>
                                        </div>
                                    </div>
                                    <div class="ranking-controls d-none">
                                        <span class="badge bg-primary rank-badge">Rang: <span class="rank-number">-</span></span>
                                        <button type="button" class="btn btn-sm btn-outline-secondary move-up ms-1" title="Monter">↑</button>
                                        <button type="button" class="btn btn-sm btn-outline-secondary move-down" title="Descendre">↓</button>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    html += '<div class="alert alert-info mt-2"><small>Cochez les candidats que vous souhaitez classer, puis utilisez les flèches pour ordonner vos choix.</small></div>';
                    candidatesList.innerHTML = html;

                    // Add event listeners for ranking
                    document.querySelectorAll('.rank-checkbox').forEach(checkbox => {
                        checkbox.addEventListener('change', function() {
                            updateRanking();
                        });
                    });

                    document.querySelectorAll('.move-up').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const item = this.closest('.candidate-rank-item');
                            const candidateId = parseInt(item.dataset.candidateId);
                            moveCandidate(candidateId, -1);
                        });
                    });

                    document.querySelectorAll('.move-down').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const item = this.closest('.candidate-rank-item');
                            const candidateId = parseInt(item.dataset.candidateId);
                            moveCandidate(candidateId, 1);
                        });
                    });

                } else {
                    // SINGLE CHOICE MODE - Display with radio buttons
                    let html = '';
                    candidates.forEach(candidate => {
                        const colorStyle = candidate.party_color || '#6c757d';
                        html += `
                            <div class="form-check candidate-option mb-3 p-3 border rounded">
                                <input class="form-check-input" type="radio" name="candidate"
                                       id="candidate_${candidate.id}" value="${candidate.id}">
                                <label class="form-check-label w-100" for="candidate_${candidate.id}">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>${candidate.first_name} ${candidate.last_name}</strong>
                                            <br>
                                            <span class="badge" style="background-color: ${colorStyle};">
                                                ${candidate.party_code}
                                            </span>
                                            <span class="text-muted">${candidate.party_name}</span>
                                        </div>
                                    </div>
                                </label>
                            </div>
                        `;
                    });
                    candidatesList.innerHTML = html;

                    // Add event listeners to candidate radio buttons
                    document.querySelectorAll('input[name="candidate"]').forEach(radio => {
                        radio.addEventListener('change', function() {
                            selectedCandidateId = parseInt(this.value);
                            electionSubmitBtn.disabled = false;
                        });
                    });
                }

                candidatesContainer.style.display = 'block';
                if (!isRankedChoice) {
                    electionSubmitBtn.disabled = true;  // Will be enabled when selection is made
                }
            } else {
                candidatesList.innerHTML = '<div class="alert alert-warning">Aucun candidat disponible pour cette élection et région.</div>';
                candidatesContainer.style.display = 'block';
                votingMethodContainer.style.display = 'none';
                electionSubmitBtn.disabled = true;
            }
        } catch (error) {
            console.error('Error loading candidates:', error);
            candidatesList.innerHTML = '<div class="alert alert-danger">Erreur lors du chargement des candidats.</div>';
            candidatesContainer.style.display = 'block';
            votingMethodContainer.style.display = 'none';
            electionSubmitBtn.disabled = true;
        }
    }

    // Update ranking when checkboxes change
    function updateRanking() {
        rankedCandidates = [];
        document.querySelectorAll('.rank-checkbox:checked').forEach(checkbox => {
            rankedCandidates.push(parseInt(checkbox.value));
        });

        // Show/hide ranking controls and update rank numbers
        document.querySelectorAll('.candidate-rank-item').forEach(item => {
            const candidateId = parseInt(item.dataset.candidateId);
            const checkbox = item.querySelector('.rank-checkbox');
            const controls = item.querySelector('.ranking-controls');
            const rankNumber = item.querySelector('.rank-number');

            if (checkbox.checked) {
                controls.classList.remove('d-none');
                const rank = rankedCandidates.indexOf(candidateId) + 1;
                rankNumber.textContent = rank;
            } else {
                controls.classList.add('d-none');
            }
        });

        // Enable submit if at least one candidate is ranked
        electionSubmitBtn.disabled = rankedCandidates.length === 0;
    }

    // Move candidate up or down in ranking
    function moveCandidate(candidateId, direction) {
        const currentIndex = rankedCandidates.indexOf(candidateId);
        if (currentIndex === -1) return;

        const newIndex = currentIndex + direction;
        if (newIndex < 0 || newIndex >= rankedCandidates.length) return;

        // Swap positions
        [rankedCandidates[currentIndex], rankedCandidates[newIndex]] =
        [rankedCandidates[newIndex], rankedCandidates[currentIndex]];

        // Update display
        updateRanking();
    }

    // Election selection change
    if (electionSelect) {
        electionSelect.addEventListener('change', function() {
            selectedElectionId = parseInt(this.value);
            selectedCandidateId = null;
            loadCandidates();
        });
    }

    // Region selection change
    if (regionSelect) {
        regionSelect.addEventListener('change', function() {
            selectedRegionId = parseInt(this.value);
            selectedCandidateId = null;
            loadCandidates();
        });
    }

    // Submit election vote
    if (electionVoteForm) {
        electionVoteForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Validate based on voting mode
            if (isRankedChoice) {
                if (rankedCandidates.length === 0) {
                    showElectionAlert('Veuillez classer au moins un candidat.', 'danger');
                    return;
                }
            } else {
                if (!selectedCandidateId) {
                    showElectionAlert('Veuillez sélectionner un candidat.', 'danger');
                    return;
                }
            }

            // Disable submit button
            electionSubmitBtn.disabled = true;
            electionSubmitText.textContent = 'Envoi en cours...';
            electionSubmitSpinner.classList.remove('d-none');

            // Prepare vote data based on voting method
            const voteData = {
                nas: electionNas.value,
                code: electionCode.value,
                election_id: selectedElectionId,
                region_id: selectedRegionId,
                voting_method: isRankedChoice ? 'ranked_choice' : 'single_choice'
            };

            if (isRankedChoice) {
                // Ranked choice: send first choice as candidate_id and full ranking in metadata
                voteData.candidate_id = rankedCandidates[0];  // First choice
                voteData.ranked_choices = rankedCandidates;   // Full ranking
            } else {
                // Single choice: just send the selected candidate
                voteData.candidate_id = selectedCandidateId;
            }

            try {
                const response = await fetch('/elections/vote', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(voteData)
                });

                const data = await response.json();

                if (data.success) {
                    showElectionAlert(data.message, 'success');
                    electionVoteForm.reset();

                    // IMPORTANT: Show results ONLY AFTER successful vote
                    await loadElectionResults(selectedElectionId, selectedRegionId);
                    electionResultsCard.style.display = 'block';

                    // Scroll to results
                    electionResultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                } else {
                    showElectionAlert(data.message, 'danger');
                }
            } catch (error) {
                showElectionAlert('Erreur de connexion au serveur. Veuillez réessayer.', 'danger');
                console.error('Error:', error);
            } finally {
                // Re-enable submit button
                electionSubmitBtn.disabled = false;
                electionSubmitText.textContent = 'Soumettre le Vote';
                electionSubmitSpinner.classList.add('d-none');
            }
        });
    }

    // Show election alert
    function showElectionAlert(message, type) {
        const alertHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                <strong>${type === 'success' ? 'Succès!' : 'Erreur!'}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        electionAlertContainer.innerHTML = alertHTML;

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = electionAlertContainer.querySelector('.alert');
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }

    // Load election results
    async function loadElectionResults(electionId, regionId) {
        try {
            const response = await fetch(`/api/elections/${electionId}/regions/${regionId}/results`);
            const results = await response.json();

            if (results && results.candidates) {
                let html = '<h5>' + results.region_name + '</h5>';
                html += '<p class="text-muted">Total des votes: ' + results.total_votes + '</p>';

                html += '<div class="list-group">';
                results.candidates.forEach((candidate, index) => {
                    const isWinner = index === 0 && results.total_votes > 0;
                    const badgeClass = isWinner ? 'bg-warning' : 'bg-secondary';
                    const winnerIcon = isWinner ? '🏆 ' : '';

                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <div>
                                    <strong>${winnerIcon}${candidate.name}</strong>
                                    <br>
                                    <span class="badge" style="background-color: ${candidate.party_color};">
                                        ${candidate.party_code}
                                    </span>
                                    <span class="text-muted">${candidate.party_name}</span>
                                </div>
                                <span class="badge ${badgeClass} fs-6">${candidate.votes} votes</span>
                            </div>
                            <div class="progress" style="height: 20px;">
                                <div class="progress-bar" role="progressbar"
                                     style="width: ${candidate.percentage}%; background-color: ${candidate.party_color};"
                                     aria-valuenow="${candidate.percentage}" aria-valuemin="0" aria-valuemax="100">
                                    ${candidate.percentage}%
                                </div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';

                electionResultsContainer.innerHTML = html;
            }
        } catch (error) {
            console.error('Error loading election results:', error);
            electionResultsContainer.innerHTML = '<div class="alert alert-danger">Erreur lors du chargement des résultats.</div>';
        }
    }

    // Initialize elections and regions when page loads
    loadElections();
    loadRegions();
});
