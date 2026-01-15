# Post-Merge Checklist

**Merge:** selectiveRetry → master
**Date:** 2026-01-15
**Status:** Pre-Merge Preparation Complete

---

## Immediate Post-Merge Steps (First Hour)

### 1. Verify Merge Success
- [ ] Confirm merge commit created on master branch
- [ ] Verify commit message includes all necessary details
- [ ] Check git log shows clean merge (no conflicts)
- [ ] Verify all 24 commits from selectiveRetry are included

```bash
# Verify merge
git checkout master
git log --oneline -25  # Should show merge commit + 24 feature commits
git log --graph --oneline --all -10  # Visual verification
```

### 2. Push to Remote
- [ ] Push master branch to origin
- [ ] Verify push succeeded
- [ ] Check remote branch status

```bash
git push origin master
git log origin/master --oneline -5
```

### 3. Deploy to Staging
- [ ] Deploy merged code to staging environment
- [ ] Wait for deployment to complete
- [ ] Check application health endpoints
- [ ] Verify no startup errors

```bash
# Example deployment command
./deploy.sh staging

# Check health
curl https://staging.example.com/health
```

### 4. Run Validation in Staging
- [ ] Run validation script in staging environment
- [ ] Verify 8/8 checks pass
- [ ] Run full test suite in staging
- [ ] Verify 34/34 tests pass

```bash
cd /path/to/staging/storycrew
python scripts/validate_selective_retry.py
python -m pytest tests/ -v
```

---

## Short-Term Verification (First 24 Hours)

### 5. Smoke Tests
- [ ] Generate 1-2 test chapters
- [ ] Verify retry logs show correct levels (EDIT_ONLY, WRITE_ONLY, FULL_RETRY)
- [ ] Check state preservation works correctly
- [ ] Confirm no errors in generation logs

```bash
# Run smoke test
python scripts/smoke_test_deployment.py
```

### 6. Monitor First 10 Chapters
- [ ] Watch retry type distribution
- [ ] Verify cost reduction is occurring
- [ ] Check quality metrics remain stable
- [ ] Look for unexpected errors

```bash
# Monitor logs
tail -f logs/storycrew.log | grep "Retry level determined"
```

### 7. Verify Cost Metrics
- [ ] Check average cost per chapter
- [ ] Compare to pre-deployment baseline
- [ ] Verify 40-60% cost reduction target is being met
- [ ] Document any anomalies

### 8. Quality Assurance
- [ ] Review judge pass rate (should be >85%)
- [ ] Check retry escalation rate (should be <20%)
- [ ] Verify chapter quality scores are stable
- [ ] Solicit feedback from content reviewers

---

## Medium-Term Monitoring (First Week)

### 9. Performance Tracking
- [ ] Track average generation time by retry type
- [ ] Monitor token usage trends
- [ ] Measure success rate (target: >95%)
- [ ] Document performance improvements

**Daily Check:**
```bash
# Generate daily report
python scripts/generate_deployment_report.py --days 1
```

### 10. Error Monitoring
- [ ] Set up alerts for high error rates
- [ ] Monitor exception logs
- [ ] Track any state preservation failures
- [ ] Review scene list parsing errors

**Alert Thresholds:**
- Success rate drops below 80% → Critical
- FULL_RETRY rate exceeds 50% → Warning
- Error rate exceeds 10% → Critical

### 11. User Feedback
- [ ] Gather feedback from chapter generation users
- [ ] Document any reported issues
- [ ] Track user satisfaction scores
- [ ] Identify improvement opportunities

### 12. Cost Analysis
- [ ] Calculate total cost savings for the week
- [ ] Compare to projected 40-60% reduction
- [ ] Generate cost savings report
- [ ] Share results with stakeholders

---

## Long-Term Validation (First Month)

### 13. Monthly Report
- [ ] Compile monthly cost savings
- [ ] Analyze quality trends
- [ ] Document performance metrics
- [ ] Create recommendations for optimization

### 14. Process Optimization
- [ ] Review retry type distribution
- [ ] Identify opportunities to increase selective retry rate
- [ ] Fine-tune issue-to-retry mapping if needed
- [ ] Adjust escalation thresholds based on data

### 15. Documentation Updates
- [ ] Update deployment guide with lessons learned
- [ ] Add troubleshooting tips from real issues
- [ ] Document any configuration changes made
- [ ] Create knowledge base articles

### 16. Training and Knowledge Transfer
- [ ] Train dev team on new retry logic
- [ ] Create runbooks for common scenarios
- [ ] Document monitoring procedures
- [ ] Share best practices with team

---

## Rollback Triggers

### Immediate Rollback (Within 1 Hour)

Trigger if ANY of these occur:
- [ ] Success rate drops below 70%
- [ ] Critical errors in >20% of generations
- [ ] Application becomes unstable
- [ ] Data corruption detected

**Rollback Steps:**
```bash
git revert -m 1 HEAD
git push origin master
./deploy.sh production  # Redeploy
```

### Consider Rollback (Within 24 Hours)

Evaluate if ANY of these occur:
- [ ] Success rate drops below 80%
- [ ] Cost reduction is <20% (far below target)
- [ ] Quality metrics degrade significantly
- [ ] User complaints increase significantly

**Decision Process:**
1. Investigate root cause
2. Determine if fixable with hotfix
3. If not, proceed with rollback
4. Document lessons learned

### Monitor Closely (Ongoing)

Watch for these trends:
- [ ] Gradual increase in FULL_RETRY rate
- [ ] Slow decline in quality metrics
- [ ] Cost reduction diminishing over time
- [ ] User satisfaction declining

---

## Success Criteria

### Must Have (Non-Negotiable)
- [x] All 34 tests passing
- [x] 8/8 validation checks passing
- [ ] Success rate remains >85%
- [ ] No critical bugs in production
- [ ] Cost reduction of at least 30%

### Should Have (Target Goals)
- [ ] Cost reduction of 40-60%
- [ ] Quality metrics stable (±5%)
- [ ] Performance improvement of 20%+
- [ ] User satisfaction maintained
- [ ] FULL_RETRY rate <40%

### Nice to Have (Stretch Goals)
- [ ] Cost reduction >60%
- [ ] Quality metrics improve
- [ ] Performance improvement >40%
- [ ] User satisfaction increases
- [ ] FULL_RETRY rate <20%

---

## Communication Plan

### Pre-Merge
- [x] Create deployment summary
- [x] Prepare merge commit message
- [x] Document rollback plan
- [ ] Notify dev team of pending merge

### Immediate Post-Merge (Day 0)
- [ ] Notify team: "Merge complete, deploying to staging"
- [ ] Share staging URL for verification
- [ ] Provide smoke test instructions
- [ ] Set up monitoring dashboards

### Day 1
- [ ] Share initial metrics with team
- [ ] Report any issues found
- [ ] Update on deployment status
- [ ] Schedule review meeting if needed

### Week 1
- [ ] Send weekly summary to stakeholders
- [ ] Share cost savings report
- [ ] Document any adjustments made
- [ ] Plan for production rollout

### Month 1
- [ ] Present monthly report to leadership
- [ ] Share lessons learned
- [ ] Propose next optimization phase
- [ ] Celebrate success with team!

---

## Issue Escalation Path

### Level 1: Self-Service (First 30 minutes)
- Check logs: `tail -f logs/storycrew.log`
- Run validation: `python scripts/validate_selective_retry.py`
- Review documentation: `docs/DEPLOYMENT_GUIDE.md`
- Check troubleshooting section

### Level 2: Team Support (30 min - 2 hours)
- Post in team Slack channel
- Share error logs and context
- Collaborate on diagnosis
- Implement fix if simple

### Level 3: Engineering Lead (2 - 4 hours)
- Escalate if issue unresolved
- Schedule emergency meeting
- Decide on rollback vs. hotfix
- Execute decision

### Level 4: Management (4+ hours)
- Escalate critical issues
- Schedule incident review
- Communicate with stakeholders
- Document post-incident report

---

## Appendix: Useful Commands

### Monitoring Commands
```bash
# Watch retry distribution
watch -n 5 'grep "Retry level determined" logs/*.log | tail -20'

# Count retries by type
grep "Running.*retry" logs/*.log | sed 's/.*Running //' | sed 's/ retry.*//' | sort | uniq -c

# Check error rate
grep -c "ERROR" logs/*.log

# View recent failures
grep "All retries exhausted" logs/*.log | tail -10
```

### Analysis Commands
```bash
# Calculate cost savings
python scripts/analyze_cost_savings.py --days 7

# Generate quality report
python scripts/generate_quality_report.py --days 7

# Check retry escalation rate
grep "Escalating to FULL_RETRY" logs/*.log | wc -l
```

### Maintenance Commands
```bash
# Rotate logs
logrotate -f /etc/logrotate.d/storycrew

# Clean old logs
find logs/ -name "*.log" -mtime +30 -delete

# Backup database
pg_dump storycrew > backup_$(date +%Y%m%d).sql
```

---

## Sign-Off

### Pre-Merge Readiness
- [x] All tests passing (34/34)
- [x] Validation script passing (8/8)
- [x] Documentation complete
- [x] Rollback plan documented
- [x] Merge commit message prepared
- [x] Deployment guide created

### Post-Merge Verification
- [ ] Merge completed successfully
- [ ] Tests passing in staging
- [ ] Smoke tests passing
- [ ] Monitoring configured
- [ ] Team notified
- [ ] Ready for production rollout

---

**Prepared By:** Claude Sonnet 4.5
**Date:** 2026-01-15
**Status:** Ready for Merge
**Next Step:** Execute merge and proceed with post-merge checklist

*This checklist ensures successful deployment and monitoring of the selective retry optimization feature.*
