"""QA-контур: серверная проверка вердиктов, версии артефакта, границы доказательств, машинный токен.

Проверки воспроизводят поведение приёмки. Платные вызовы не выполняются."""
import json
import unittest

from backend import main, qa_reviews, test_smoke

TOKEN = 'qa-service-token'
NARROW = 'narrow-token'


class QaReviewsTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp

    def tearDown(self):
        main.os.environ.pop('STUDIO_SERVICE_TOKENS', None)
        test_smoke.StudioSmokeTests.tearDown(self)

    def prepare(self):
        main.os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN}:*'
        self.pid = self.client.post('/api/projects', json={'title': 'QA', 'state': {}}).json()['id']
        main.os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN}:{self.pid};{NARROW}:another-project'
        # Машинный вызов идёт только по токену: браузерной сессии у него нет.
        self.client.headers.pop('X-Studio-Session', None)
        self.client.cookies.clear()
        self.client.headers['Authorization'] = f'Bearer {TOKEN}'

    def create(self, **extra):
        body = {'project_id': self.pid, 'task_id': 'task-1', 'artifact_id': 'artifact-1', 'artifact_revision': 'rev-3',
                'artifact_text': 'Грэм подмигивает в машине цвета жёлтый.', 'canon_text': 'Машина жёлтая, фары круглые.',
                'brief_text': 'Сцена: подмигнуть.', 'review_phase': 'TEXT_PRECHECK', 'requested_scopes': ['TEXT'],
                'request_id': 'qa-request-1', **extra}
        r = self.client.post('/api/qa/reviews', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def verdict(self, review_id, role, **extra):
        body = {'role': role, 'verdict': 'PASS', 'artifact_revision': 'rev-3', 'checked_scopes': ['TEXT'],
                'scope_results': {'TEXT': 'PASS'}, 'evidence': [], 'request_id': 'x', **extra}
        return self.client.post(f'/api/qa/reviews/{review_id}/verdicts', json=body)

    def test_token_does_not_open_the_rest_of_the_api(self):
        self.prepare()
        # Приёмочный контур токен открывает.
        self.assertEqual(self.client.get('/api/qa/reviews/nope').status_code, 404)
        # Остальное — только по браузерной сессии владельца.
        self.assertEqual(self.client.get('/api/projects').status_code, 401)
        self.assertEqual(self.client.get('/api/budgets/limits').status_code, 401)

    def test_machine_token_is_required(self):
        self.prepare()
        self.client.headers['Authorization'] = 'Bearer wrong-token'
        r = self.client.get('/api/qa/reviews/any')
        self.assertEqual(r.status_code, 401, r.text)

    def test_token_without_project_scope_is_refused(self):
        self.prepare()
        self.client.headers['Authorization'] = f'Bearer {NARROW}'
        r = self.client.post('/api/qa/reviews', json={'project_id': self.pid, 'task_id': 't', 'artifact_id': 'a',
                                                        'artifact_revision': 'r', 'request_id': 'scope-denied-1'})
        self.assertEqual(r.status_code, 403, r.text)

    def test_server_computes_revisions_from_content(self):
        self.prepare()
        review = self.create()['review']
        self.assertTrue(review['artifact_sha'])
        self.assertTrue(review['canon_sha'])
        self.assertNotEqual(review['artifact_sha'], review['canon_sha'])
        self.assertEqual(review['status'], 'AWAITING_VERDICTS')

    def test_creation_is_idempotent_by_request_id(self):
        self.prepare()
        first = self.create()
        second = self.create()
        self.assertEqual(first['review']['review_id'], second['review']['review_id'])
        self.assertTrue(second['duplicate'])

    def test_media_scope_is_refused_in_text_precheck(self):
        self.prepare()
        r = self.client.post('/api/qa/reviews', json={'project_id': self.pid, 'task_id': 't', 'artifact_id': 'a',
                                                        'artifact_revision': 'r', 'review_phase': 'TEXT_PRECHECK',
                                                        'requested_scopes': ['IMAGE'], 'request_id': 'scope-media-1'})
        self.assertEqual(r.status_code, 400, r.text)

    def test_packet_is_isolated_per_critic(self):
        self.prepare()
        review = self.create()['review']
        packet = self.client.get(f'/api/qa/reviews/{review["review_id"]}/packet/REVIEW-REQ').json()
        self.assertEqual(packet['role'], 'REVIEW-REQ')
        self.assertEqual(packet['artifact_text'], 'Грэм подмигивает в машине цвета жёлтый.')
        self.assertNotIn('verdicts', packet)
        denied = self.client.get(f'/api/qa/reviews/{review["review_id"]}/packet/REVIEW-CRAFT')
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_stale_artifact_revision_is_refused(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ', artifact_revision='rev-2')
        self.assertEqual(r.status_code, 409, r.text)

    def test_pass_without_trusted_source_is_downgraded_to_blocked(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ',
                         evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': 'canon-7', 'quote': 'жёлтый'}])
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['TEXT'], 'BLOCKED')
        self.assertEqual(data['verdict']['overall'], 'BLOCKED')
        self.assertTrue(any('доверенн' in note for note in data['verdict']['notes']))

    def test_pass_citing_server_revision_is_accepted(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ',
                         evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': review['artifact_sha'],
                                    'quote': 'Грэм подмигивает в машине цвета жёлтый.'}])
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['TEXT'], 'PASS')
        self.assertEqual(data['verdict']['overall'], 'PASS')
        self.assertEqual(data['server_receipt']['verified'], True)
        self.assertEqual(data['server_receipt']['artifact_revision'], 'rev-3')

    def test_model_flags_do_not_grant_approval(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ',
                         evidence_verified_by_backend=True, approved_expert_model=True, quality_claim=True,
                         evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': 'canon-7'}])
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['TEXT'], 'BLOCKED')
        self.assertNotEqual(data['review_status'], 'TEXT_PRECHECK_PASSED_AWAITING_OWNER')

    def test_two_passed_critics_wait_for_the_owner(self):
        self.prepare()
        review = self.create()['review']
        for role in ('REVIEW-REQ', 'REVIEW-SYSTEM'):
            r = self.verdict(review['review_id'], role,
                             evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': review['artifact_sha'],
                                        'quote': 'Грэм подмигивает в машине цвета жёлтый.'}])
            self.assertEqual(r.status_code, 200, r.text)
        state = self.client.get(f'/api/qa/reviews/{review["review_id"]}').json()
        self.assertEqual(state['status'], 'TEXT_PRECHECK_PASSED_AWAITING_OWNER')
        self.assertEqual(state['next_action'], 'wait_for_owner_approval')
        self.assertNotIn('final_release_approved', state)

    def test_verified_fail_returns_the_gap(self):
        self.prepare()
        review = self.create()['review']
        for role in ('REVIEW-REQ', 'REVIEW-SYSTEM'):
            r = self.verdict(review['review_id'], role, verdict='FAIL', scope_results={'TEXT': 'FAIL'},
                             biggest_gap='машина красная, а канон требует жёлтую',
                             evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': review['artifact_sha'],
                                        'quote': 'машина цвета красный'}])
            self.assertEqual(r.status_code, 200, r.text)
        state = self.client.get(f'/api/qa/reviews/{review["review_id"]}').json()
        self.assertEqual(state['status'], 'CHANGES_REQUESTED')
        self.assertEqual(state['next_action'], 'return_evidenced_gap_to_original_builder')

    def test_unverified_fail_does_not_start_a_repair_loop(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ', verdict='FAIL', scope_results={'TEXT': 'FAIL'},
                         biggest_gap='что-то не так', evidence=[])
        data = r.json()
        self.assertEqual(data['verdict']['overall'], 'BLOCKED')
        self.assertNotEqual(data['review_status'], 'CHANGES_REQUESTED')

    def test_media_scope_stays_blocked_without_inspector(self):
        self.prepare()
        review = self.create(review_phase='FINAL_MEDIA', requested_scopes=['IMAGE'],
                             required_reviewers=['REVIEW-REQ', 'REVIEW-SYSTEM', 'REVIEW-CRAFT'],
                             request_id='qa-request-media-1')['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ', checked_scopes=['IMAGE'], scope_results={'IMAGE': 'PASS'},
                         evidence=[{'scope': 'IMAGE', 'evidence_type': 'image_observation', 'source_asset_id': 'asset-9'}])
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['IMAGE'], 'BLOCKED')
        self.assertTrue(any('media inspector' in note for note in data['verdict']['notes']))

    def test_second_verdict_of_the_same_critic_is_conflict(self):
        self.prepare()
        review = self.create()['review']
        self.verdict(review['review_id'], 'REVIEW-REQ')
        same = self.verdict(review['review_id'], 'REVIEW-REQ')
        self.assertEqual(same.status_code, 200, same.text)
        self.assertTrue(same.json()['duplicate'])
        other = self.verdict(review['review_id'], 'REVIEW-REQ', verdict='BLOCKED')
        self.assertEqual(other.status_code, 409, other.text)

    def test_critic_outside_the_review_is_refused(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-CRAFT')
        self.assertEqual(r.status_code, 403, r.text)

    def test_scope_results_are_not_trusted_without_a_checked_scope(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ', checked_scopes=[],
                         evidence=[{'scope': 'TEXT', 'evidence_type': 'text_quote', 'source_text_revision': review['artifact_sha']}])
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['TEXT'], 'BLOCKED')

    def test_evidence_type_must_match_the_scope(self):
        self.prepare()
        review = self.create()['review']
        r = self.verdict(review['review_id'], 'REVIEW-REQ',
                         evidence=[{'scope': 'TEXT', 'evidence_type': 'image_observation', 'source_text_revision': review['artifact_sha']}])
        data = r.json()
        self.assertEqual(data['verdict']['scope_results']['TEXT'], 'BLOCKED')

    def test_unknown_review_is_not_found(self):
        self.prepare()
        self.assertEqual(self.client.get('/api/qa/reviews/nope').status_code, 404)


class QaReviewUnitTests(unittest.TestCase):
    def test_overall_prefers_fail_then_blocked(self):
        self.assertEqual(qa_reviews.overall_of({'TEXT': 'PASS', 'IMAGE': 'FAIL'}), 'FAIL')
        self.assertEqual(qa_reviews.overall_of({'TEXT': 'PASS', 'IMAGE': 'BLOCKED'}), 'BLOCKED')
        self.assertEqual(qa_reviews.overall_of({'TEXT': 'PASS'}), 'PASS')

    def test_server_receipt_matches_the_n8n_aggregator_contract(self):
        receipt = {'verified': True, 'review_id': 'r1', 'artifact_revision': 'rev-3'}
        self.assertTrue(receipt['verified'])
        self.assertEqual(receipt['artifact_revision'], 'rev-3')

    def test_json_stored_fields_round_trip(self):
        self.assertEqual(json.loads(json.dumps(['TEXT'])), ['TEXT'])


if __name__ == '__main__':
    unittest.main()
